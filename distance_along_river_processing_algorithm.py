# -*- coding: utf-8 -*-

"""
/***************************************************************************
 DistanceAlongRiver
                                 A QGIS plugin
 Calculate distances between pair of points by projecting them on a river axis
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2021-03-30
        copyright            : (C) 2021 by J. Pierson, UMR 6554 LETG, CNRS
        email                : julie.pierson@univ-brest.fr
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'J. Pierson, UMR 6554 LETG, CNRS'
__date__ = '2021-03-30'
__copyright__ = '(C) 2021 by J. Pierson, UMR 6554 LETG, CNRS'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import (QCoreApplication,
                              QVariant)
from qgis.core import (QgsProcessing,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterVectorDestination,
                       QgsProcessingParameterFeatureSink,
                       QgsWkbTypes,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterField,
                       QgsVectorLayer,
                       QgsProject,
                       QgsCoordinateReferenceSystem,
                       QgsFields,
                       QgsField,
                       QgsFeature,
                       NULL)
import processing
import pandas as pd


class DistanceAlongRiverAlgorithm(QgsProcessingAlgorithm):
    """
    This is an example algorithm that takes a vector layer and
    creates a new identical one.

    It is meant to be used as an example of how to create your own
    algorithms and explain methods and variables used to do it. An
    algorithm like this will be available in all elements, and there
    is not need for additional work.

    All Processing algorithms should extend the QgsProcessingAlgorithm
    class.
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    INPUT1 = 'INPUT1'
    IDFIELD1 = 'IDFIELD1'
    INPUT2 = 'INPUT2'
    IDFIELD2 = 'IDFIELD2'
    RIVER = 'RIVER'
    PROJECTED_POINTS = 'PROJECTED_POINTS'
    OUTPUT_TABLE = 'OUTPUT_TABLE'
    CENTERLINE_OUTPUT = 'CENTERLINE_OUTPUT'
    PROJECTED1 = 'PROJECTED1'
    PROJECTED2 = 'PROJECTED2'

    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # 1st input point layer
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT1,
                self.tr('First input point layer'),
                [QgsProcessing.TypeVectorPoint ]
            )
        )
            
        # id field for 1st input layer
        self.addParameter(
            QgsProcessingParameterField(
                self.IDFIELD1,
                self.tr('ID field for first input layer'),
                '',
                self.INPUT1
            )
        )
            
        # 2nd input point layer
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT2,
                self.tr('Second input point layer'),
                [QgsProcessing.TypeVectorPoint ]
            )
        )
            
        # id field for 2nd input layer
        self.addParameter(
            QgsProcessingParameterField(
                self.IDFIELD2,
                self.tr('ID field for second input layer'),
                '',
                self.INPUT2
            )
        )
            
        # input river layer
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.RIVER,
                self.tr('Input river layer, if polygon layer its centerline will be calculated'),
                [QgsProcessing.TypeVectorAnyGeometry]
            )
        )
            
        # output table
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_TABLE, 
                self.tr('Table with distances between points'),
                )
            )
        
        # ouput centerline layer, created if input is polygon
        self.addParameter(
            QgsProcessingParameterVectorDestination(
                self.CENTERLINE_OUTPUT,
                self.tr('Output centerline layer, can be created if input layer is polygon'),
                defaultValue='', # ignore output by default
                optional=True
            )
        )
            
        # ouput projected layer 1
        self.addParameter(
            QgsProcessingParameterVectorDestination(
                self.PROJECTED1,
                self.tr('Output projected point layer 1'),
                optional=True
            )
        )
            
        # ouput projected layer 2
        self.addParameter(
            QgsProcessingParameterVectorDestination(
                self.PROJECTED2,
                self.tr('Output projected point layer 2'),
                optional=True
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        
        # Retrieve inputs and outputs
        input1 = self.parameterAsVectorLayer(parameters, self.INPUT1, context)
        idfield1 = self.parameterAsString(parameters, self.IDFIELD1, context)
        input2 = self.parameterAsVectorLayer(parameters, self.INPUT2, context)
        idfield2 = self.parameterAsString(parameters, self.IDFIELD2, context)
        river = self.parameterAsVectorLayer(parameters, self.RIVER, context)
        projected1 = self.parameterAsOutputLayer(parameters, self.PROJECTED1, context)
        projected2 = self.parameterAsOutputLayer(parameters, self.PROJECTED2, context)
        # before creating output distance table, its fields must be defined
        field_list = [['ID1', QVariant.Int], ['ID2', QVariant.Int], ['straight_dist', QVariant.Double], ['river_dist', QVariant.Double]]
        fields = QgsFields()
        for fieldname, fieldtype in field_list:
            fields.append(QgsField(fieldname, fieldtype))
        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT_TABLE, context, fields, QgsWkbTypes.NoGeometry, QgsCoordinateReferenceSystem())
        
        # column names for future distance table
        # normally, same value for 1st and 2pt ids but sometimes an id is present in only one layer
        id1_colname = field_list[0][0] # ID of 1st point
        id2_colname = field_list[1][0] # ID of 2nd point
        dist_colname = field_list[2][0] # straight line distance between pair of points
        riverdist_colname = field_list[3][0] # along-river distance between pair of projected points
       
        
        # 1/ PREPARATION : CREATE CENTERLINE IF NEEDED, MERGE LINES IN CENTERLINE IF NEEDED
        ####################################################################################
        
        # if river layer is polygon, calculate the centerline for the input layer
        if river.geometryType() == QgsWkbTypes.PolygonGeometry :
            message = 'river is polygon, calculating centerline...'
            feedback.pushInfo(QCoreApplication.translate('Distance along river', message))
            centerline = self.createCenterline(river, parameters, context, feedback)
            centerline_layer = QgsVectorLayer(centerline, "centerline", "ogr")
            QgsProject.instance().addMapLayer(centerline_layer)
        # if input layer is line, it is considered as centerline
        if river.geometryType() == QgsWkbTypes.LineGeometry:
            centerline_layer = river
            # if centerline is composed of multiple lines, merge them
            features = centerline_layer.getFeatures()
            nb_features = sum(1 for _ in features)
            if nb_features > 1:
                message = 'merging lines in river layer...'
                feedback.pushInfo(QCoreApplication.translate('Distance along river', message))
                centerline = self.mergeLines(centerline_layer, context, feedback)
                centerline_layer = QgsVectorLayer(centerline, "centerline", "ogr")
                QgsProject.instance().addMapLayer(centerline_layer)
        # if input layer is point, exit plugin
        if river.geometryType() == QgsWkbTypes.PointGeometry:
            message = 'Please choose a polygon or line layer for input river layer'
            feedback.reportError(QCoreApplication.translate('Distance along river', message))
            return {}
            
            
        # 2/ PROJECT POINTS FROM INPUT LAYERS ON RIVER CENTERLINE
        ####################################################################################
        
        message = 'Projecting 1st input layer on river...'
        feedback.pushInfo(QCoreApplication.translate('Distance along river', message))
        # get names or full path for 1st point layer and centerline
        layer_list = [input1, centerline_layer]
        call_layer_list = self.callableLayers(layer_list, feedback)
        # id field is also needed
        field_list = [idfield1]
        # SQL query to get endpoints of shortest lines between points and river centerline
        query = f"""SELECT st_endpoint(ST_ShortestLine(p.geometry, l.geometry)) as geometry,
                    p.{field_list[0]},
                    ROUND(ST_Length(ST_ShortestLine(p.geometry, l.geometry)), 6) AS distance
                    FROM "{call_layer_list[0]}" AS p, "{call_layer_list[1]}" AS l"""
        # run this query to create 1st projected point layer
        layer_projected1 = self.runSqlQuery(layer_list, field_list, query, 0, projected1, context, feedback)
        
        message = 'Projecting 2nd input layer on river...'
        feedback.pushInfo(QCoreApplication.translate('Distance along river', message))
        # get names or full path for 2nd point layer and centerline
        layer_list = [input2, centerline_layer]
        call_layer_list = self.callableLayers(layer_list, feedback)
        # id field is also needed
        field_list = [idfield2]
        # SQL query to get endpoints of shortest lines between points and river centerline
        query = f"""SELECT st_endpoint(ST_ShortestLine(p.geometry, l.geometry)) as geometry,
                    p.{field_list[0]},
                    ROUND(ST_Length(ST_ShortestLine(p.geometry, l.geometry)), 6) AS distance
                    FROM "{call_layer_list[0]}" AS p, "{call_layer_list[1]}" AS l"""
        # run this query to create 2nd projected point layer
        layer_projected2 = self.runSqlQuery(layer_list, field_list, query, 0, projected2, context, feedback)
        
#        # load layers
#        message = 'projected1 : ' + str(type(projected1))
#        feedback.pushInfo(QCoreApplication.translate('Distance along river', message))
#        projected1 = context.takeResultLayer(projected1)
#        projected2 = context.takeResultLayer(projected2)
#        #QgsProject.instance().addMapLayer(projected1)
#        #QgsProject.instance().addMapLayer(projected2)
#        message = 'projected1 : ' + str(type(projected1))
#        feedback.pushInfo(QCoreApplication.translate('Distance along river', message))
        
        
        # 3/ CALCULATE DISTANCES BETWEEN INPUT POINTS, AND BETWEEN PROJECTED POINTS
        ####################################################################################
        
        # DISTANCES BETWEEN INPUT POINTS
        message = 'Calculating distances between input layers...'
        feedback.pushInfo(QCoreApplication.translate('Distance along river', message))
        # get names or full path for input point layers
        layer_list = [input1, input2]
        call_layer_list = self.callableLayers(layer_list, feedback)
        # id fields are needed for both input layers
        field_list = [idfield1, idfield2]
        # query to calculate distances between pair of original points with same id
        # this is a full join : all points will be kept whereas present in either layer or in both
        query = f"""SELECT p1.{idfield1} as {id1_colname}, p2.{idfield2} as {id2_colname}, 
                        ST_Distance(p1.geometry, p2.geometry) as {dist_colname} 
                        FROM "{call_layer_list[0]}" as p1 LEFT JOIN "{call_layer_list[1]}" as p2 
                        ON p1.{idfield1} = p2.{idfield2}
                    UNION
                    SELECT p1.{idfield1} as {idfield1}, p2.{idfield2} as {idfield2}, 
                        ST_Distance(p1.geometry, p2.geometry) as {dist_colname} 
                        FROM "{call_layer_list[1]}" as p2 LEFT JOIN "{call_layer_list[0]}" as p1 
                        ON p1.{idfield1} = p2.{idfield2};"""
        # run this query to create table with distances
        table_distances = self.runSqlQuery(layer_list, field_list, query, 1, 'memory:', context, feedback)
        
        # DISTANCES BETWEEN PROJECTED POINTS
        message = 'Calculating distances between projected layers...'
        feedback.pushInfo(QCoreApplication.translate('Distance along river', message))
        # input layers for the SQL query
        layer_list = [projected1, projected2]
        # id fields are needed for both input layers
        field_list = [idfield1, idfield2]
        # query to calculate distances between pair of projected points with same id
        # this is a full join : all points will be kept whereas present in either layer or in both
        query = f"""SELECT p1.{idfield1} as {id1_colname}, p2.{idfield2} as {id2_colname}, 
                        ST_Distance(p1.geometry, p2.geometry) as {riverdist_colname} 
                        FROM "{call_layer_list[0]}" as p1 LEFT JOIN "{call_layer_list[1]}" as p2 
                        ON p1.{idfield1} = p2.{idfield2}
                    UNION
                    SELECT p1.{idfield1} as {id1_colname}, p2.{idfield2} as {id2_colname}, 
                        ST_Distance(p1.geometry, p2.geometry) as {riverdist_colname}  
                        FROM "{call_layer_list[1]}" as p2 LEFT JOIN "{call_layer_list[0]}" as p1 
                        ON p1.{idfield1} = p2.{idfield2};"""
        # run this query to create table with projected distances
        table_projected_distances = self.runSqlQuery(call_layer_list, field_list, query, 1, 'memory:', context, feedback)
        
        
        # 4/ SAVE RESULTS TO OUTPUT TABLE
        ####################################################################################
        
        message = 'Saving distances to table...'
        feedback.pushInfo(QCoreApplication.translate('Distance along river', message))
        # Get the 2 distance tables from context
        # https://gis.stackexchange.com/a/362146/175131
        table_distances = context.getMapLayer(table_distances)
        table_projected_distances = context.getMapLayer(table_projected_distances)
            
        # create one python dataframe from the 2 distance tables
        distance_df = self.createDataframe(table_distances, table_projected_distances, id1_colname, id2_colname, feedback)
        
        # do some treatments on dataframe
        distance_df = self.dfCalculations(distance_df, 2, dist_colname, riverdist_colname, feedback)
        
        # Then add dataframe to sink
        self.addFeaturestoSink(distance_df, sink)
        
        
        # 5/ RETURN THE RESULTING TABLE AND LAYERS
        ####################################################################################
     
        # if centerline layer is created :
        if river.geometryType() == QgsWkbTypes.PolygonGeometry :
            # don't know why exactly, but centerline layer must be removed so that it can be loaded automatically in qgis
            QgsProject.instance().removeMapLayer(centerline_layer)
            return {self.OUTPUT_TABLE: dest_id, self.PROJECTED1: layer_projected1, self.PROJECTED2: layer_projected2, self.CENTERLINE_OUTPUT: centerline}
        # if no centerline generated :
        else:
            # return distance table and projected points layers
            return {'df' : distance_df, self.OUTPUT_TABLE: dest_id, self.PROJECTED1: layer_projected1, self.PROJECTED2: layer_projected2}
 
    
    # FUNCTIONS
    ####################################################################################
    
    # create centerline of a polygon with grass voronoi.skeleton algorithm
    def createCenterline(self, polygon, parameters, context, feedback):
        # voronoi.skeleton parameters
        skeleton_param = {'input' : polygon,
                  'smoothness' : 0.1,
                  'thin' : -1,
                  'output' : parameters[self.CENTERLINE_OUTPUT]} # to output this layer in QGIS as well
        # run voronoi.skeleton
        skeleton_result = processing.run("grass7:v.voronoi.skeleton", skeleton_param, is_child_algorithm=True, context=context, feedback=feedback)
        # get output
        centerline_layer = skeleton_result['output']
        # Check for cancelation
        if feedback.isCanceled():
            return {}
        # return centerline
        return centerline_layer
    
    # given a line layer, merge all lines into one with dissolve algorithm
    def mergeLines(self, line, context, feedback):
        # dissolve parameters
        dissolve_param = {'INPUT' : line,
                  'FIELD' : None,
                  #'OUTPUT' : parameters[self.OUTPUT]} # to output this layer in QGIS as well
                  'OUTPUT' : 'dissolve'}
        # run dissolve
        dissolve_result = processing.run("native:dissolve", dissolve_param, is_child_algorithm=True, context=context, feedback=feedback)
        dissolve_layer = dissolve_result['OUTPUT']
        # Check for cancelation
        if feedback.isCanceled():
            return {}
        # return dissolved layer
        return dissolve_layer
    
    # if a layer is loaded, get its name, else gets it source = full path
    def callableLayers(self, layer_list, feedback):
        call_layer_list = []
        for layer in layer_list:
            # if layer is loaded in QGIS, get its name
            if len(QgsProject.instance().mapLayersByName(layer.name())) != 0:
                call_layer_list.append(layer.name())
            # else, get its full path
            else:
                call_layer_list.append(layer.source())
        return call_layer_list
    
    # run a sql query given a query, list of layers and list of field, layers must be names or sources (full paths)
    # geom_type : geometry type for resulting layer, 0 for autodetect, 1 for no geometry (cf. alghelp for more)
    def runSqlQuery(self, layer_list, field_list, query, geom_type, output, context, feedback):
        # executesql parameters
        executesql_param = {'INPUT_DATASOURCES' : layer_list,
                            'INPUT_QUERY' : query,
                            'INPUT_GEOMETRY_TYPE' : geom_type,
                            'OUTPUT' : output} # i.e. parameters[self.PROJECTED1] to output this layer in QGIS, else just a string
        # run executesql algorithm
        result = processing.run("qgis:executesql", executesql_param, is_child_algorithm=True, context=context, feedback=feedback)
        #result = processing.runAndLoadResults("qgis:executesql", executesql_param, context=context, feedback=feedback)
        layer = result['OUTPUT']
        # Check for cancelation
        if feedback.isCanceled():
            return {}
        # return projected points layer
        return layer
    
    # create dataframe from multiple tables
    # tables must have following fields in this order : 1st point id, 2nd point id, distance between the 2 points
    # dataframe will have following columns : 1st point id, 2nd point id, and as many distance columns as input tables, named according to fieldname_list
    def createDataframe(self, table1, table2, id1_colname, id2_colname, feedback):
        message = 'Creating dataframe from distance tables...'
        feedback.pushInfo(QCoreApplication.translate('Distance along river', message))
        # will contain one dataframe for each table
        df_list = []
        # for each table
        for table in [table1, table2]:
            # create dictionary where keys = table column names
            fieldnames = [field.name() for field in table.fields() if field.name() != 'fid']
            table_dic = dict((fieldname, []) for fieldname in fieldnames)
            # and fill the dictionary with the values for each column
            features = table.getFeatures()
            for feature in features:
                for fieldname in fieldnames:
                    table_dic[fieldname].append(feature[fieldname])
            # convert dictionary to pandas dataframe
            df = pd.DataFrame(data=table_dic)
            # and save it in df_list
            df_list.append(df)
            
        # merge the 2 dataframes
        result_df = pd.merge(df_list[0], df_list[1], on=[id1_colname, id2_colname])
        
        return result_df
    
    # do some calculations on distances dataframe (round distances...)
    def dfCalculations(self, df, decimal_count, dist_colname, riverdist_colname, feedback):
        # 1/ round distances
        ###########################################
        # round column with straight line distances
        df[dist_colname] = df[dist_colname].apply(lambda x:round(float(x), decimal_count) if x != NULL else NULL)
        # round column with distances along river axis
        df[riverdist_colname] = df[riverdist_colname].apply(lambda x:round(float(x), decimal_count) if x != NULL else NULL)
                
        return df
    
    # given a dataframe and the output table, add each line of dataframe to table
    def addFeaturestoSink(self, df, table):
        # for each row in dataframe
        for i in range(len(df.index)):
            row = df.iloc[i]
            # create list from line
            l = row.tolist()
            # add it to feature
            f = QgsFeature()
            f.setAttributes(l)
            # and add feature to table
            table.addFeature(f)
        
    

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Distance along river'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr(self.name())

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr(self.groupId())

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return ''

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return DistanceAlongRiverAlgorithm()
