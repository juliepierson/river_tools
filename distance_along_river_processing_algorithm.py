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
                       QgsProcessingContext,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterVectorDestination,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFileDestination,
                       QgsWkbTypes,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterField,
                       QgsVectorLayer,
                       QgsProject,
                       QgsCoordinateReferenceSystem,
                       QgsFields,
                       QgsField,
                       QgsFeature,
                       QgsProcessingUtils,
                       QgsCoordinateTransform,
                       QgsDistanceArea,
                       QgsPointXY,
                       NULL)
import processing
import pandas as pd
import csv


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
            QgsProcessingParameterFileDestination(
                    self.OUTPUT_TABLE,
                    self.tr('Table with distances between points (CSV file)'),
                    self.tr('CSV files (*.csv)'),
                    optional = True
            )
        )
        
        # ouput centerline layer, created if input is polygon
        self.addParameter(
            QgsProcessingParameterVectorDestination(
                self.CENTERLINE_OUTPUT,
                self.tr('Output centerline layer, can be created if input layer is polygon'),
                defaultValue = '', # ignore output by default
                optional = True
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
        #field_list = [['ID1', QVariant.Int], ['ID2', QVariant.Int], ['straight_dist', QVariant.Double], ['river_dist', QVariant.Double]]
        field_list = [['ID1', QVariant.String], ['ID2', QVariant.String], ['straight_dist', QVariant.Double], ['river_dist', QVariant.Double]]
        fields = QgsFields()
        for fieldname, fieldtype in field_list:
            fields.append(QgsField(fieldname, fieldtype))
        
        # column names for future distance table
        # normally, same value for 1st and 2pt ids but sometimes an id is present in only one layer
        id1_colname = field_list[0][0] # ID of 1st point
        id2_colname = field_list[1][0] # ID of 2nd point
        dist_colname = field_list[2][0] # straight line distance between pair of points
        riverdist_colname = field_list[3][0] # along-river distance between pair of projected points
        # get output path for future distance table as string
        table_output_path = self.parameterAsOutputLayer(parameters, self.OUTPUT_TABLE, context)
        
        # check input parameters
        self.checkParameters(context, feedback)
        
        
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
        layer_projected1 = QgsProcessingUtils.mapLayerFromString(layer_projected1, context)
        
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
        feedback.pushInfo(QCoreApplication.translate('Distance along river', layer_projected2))
        layer_projected2 = QgsProcessingUtils.mapLayerFromString(layer_projected2, context)
        
        
        # 3/ CALCULATE DISTANCES BETWEEN INPUT POINTS, AND BETWEEN PROJECTED POINTS
        ####################################################################################
        
        # DISTANCES BETWEEN INPUT POINTS
        message = 'Getting input layer coordinates...'
        feedback.pushInfo(QCoreApplication.translate('Distance along river', message))
        dic_layer1 = self.getCoordinates(input1, idfield1, context)
        dic_layer2 = self.getCoordinates(input2, idfield2, context)
        
        message = 'Calculating distances between input layers...'
        feedback.pushInfo(QCoreApplication.translate('Distance along river', message))
        crs = input1.crs()
        table_distances = self.calculateDistances(crs, dic_layer1, dic_layer2, id1_colname, id2_colname, dist_colname, context, feedback)
        
        # DISTANCES BETWEEN PROJECTED POINTS
        message = 'Getting projected layers coordinates...'
        feedback.pushInfo(QCoreApplication.translate('Distance along river', message))
        dic_layer1proj = self.getCoordinates(layer_projected1, idfield1, context)
        dic_layer2proj = self.getCoordinates(layer_projected2, idfield2, context)
        
        message = 'Calculating distances between projected layers...'
        feedback.pushInfo(QCoreApplication.translate('Distance along river', message))
        crs = layer_projected1.crs()
        table_projected_distances = self.calculateDistances(crs, dic_layer1proj, dic_layer2proj, id1_colname, id2_colname, riverdist_colname, context, feedback)
        
        
        # 4/ SAVE RESULTS TO OUTPUT TABLE
        ####################################################################################
        
        message = 'Saving distances to table...'
        feedback.pushInfo(QCoreApplication.translate('Distance along river', message))
       
        # create one dataframe from the 2 dataframes
        if table_distances[id1_colname].equals(table_projected_distances[id1_colname]) and table_distances[id2_colname].equals(table_projected_distances[id2_colname]):
            df_result = table_distances
            df_result[riverdist_colname] = table_projected_distances[riverdist_colname]
        else:
            message = 'Sorry, there was an error while creating result dataframe'
            feedback.reportError(QCoreApplication.translate('Distance along river', message))
            return {}
        
        # do some treatments on dataframe
        message = 'Rounding numbers and sorting lines by id in result dataframe...'
        feedback.pushInfo(QCoreApplication.translate('Distance along river', message))
        df_result = self.dfCalculations(df_result, id1_colname, 2, dist_colname, riverdist_colname, feedback)
        
        # Then add dataframe to sink
        message = 'Saving dataframe to table...'
        feedback.pushInfo(QCoreApplication.translate('Distance along river', message))
        self.addFeaturestoTable(df_result, table_output_path)
        
        # load distance table in project
        uri = 'file://' + table_output_path + '?delimiter=,'
        table_layer = QgsVectorLayer(uri, "Distance table", "delimitedtext")
        # with QgsProject.instance().addMapLayer layer is added but cannot be seen
        # see https://gis.stackexchange.com/a/401802/175131
        context.temporaryLayerStore().addMapLayer(table_layer)
        context.addLayerToLoadOnCompletion(table_layer.id(), QgsProcessingContext.LayerDetails("", QgsProject.instance(), ""))
        
        
        # 5/ RETURN THE RESULTING TABLE AND LAYERS
        ####################################################################################
     
        # if centerline layer is created :
        if river.geometryType() == QgsWkbTypes.PolygonGeometry :
            # don't know why exactly, but centerline layer must be removed so that it can be loaded automatically in qgis
            QgsProject.instance().removeMapLayer(centerline_layer)
            return {self.OUTPUT_TABLE: table_output_path, self.PROJECTED1: layer_projected1, self.PROJECTED2: layer_projected2, self.CENTERLINE_OUTPUT: centerline}
        # if no centerline generated :
        else:
            # return distance table and projected points layers
            return {self.OUTPUT_TABLE: table_output_path, self.PROJECTED1: layer_projected1, self.PROJECTED2: layer_projected2}
 
    
    # FUNCTIONS
    ####################################################################################
    
    def checkParameters(self, context, feedback):
        # check geometry types
        # TODO
        # check if both input point layers have same crs
        # TODO
        pass
    
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
        layer = result['OUTPUT']
        # Check for cancelation
        if feedback.isCanceled():
            return {}
        # return result layer
        return layer
    
    # from one layer, create a dictionary with id values as keys and qgspoints as values
    # if layer crs is projected, convert coordinates to geographic ones
    def getCoordinates(self, layer, idfield, context):
        # initiates result dictionary
        dic_layer = {}
        # iterates over features
        for f in layer.getFeatures():
            dic_layer[f[idfield]] = QgsPointXY(f.geometry().asPoint()[0], f.geometry().asPoint()[1])
        # get layer crs
        crs = layer.crs()
        # if crs is projected
        if layer.crs().isGeographic() == False:
            # transform projected coordinates in geographic coordinates
            transformContext = QgsProject.instance().transformContext()
            geog_crs = QgsCoordinateReferenceSystem(crs.geographicCrsAuthId())
            xform = QgsCoordinateTransform(crs, geog_crs, transformContext)
            for key, value in dic_layer.items():
                dic_layer[key] = xform.transform(dic_layer[key])
        return dic_layer
    
    # calculate distances between pair of points in 2 layers with same id using pyproj
    def calculateDistances(self, crs, dic_layer1, dic_layer2, id1_colname, id2_colname, dist_colname, context, feedback):
        # uses QgsDistanceArea to calculate ellipsoid based distances
        d = QgsDistanceArea()
        d.setEllipsoid(crs.ellipsoidAcronym())
        # get all keys from both dictionaries, no duplicates
        id_set = set(list(dic_layer1.keys()) + list(dic_layer2.keys()))
        # create empty result dictionary
        dic_result = {id1_colname : [], id2_colname : [], dist_colname : []}
        # for each key
        for pnt_id in id_set:
            # if point is present in both layers
            if pnt_id in dic_layer1.keys() and pnt_id in dic_layer2.keys():
                # calculate distance between points with same id
                #pt1 = QgsPointXY(dic_layer1[pnt_id][0], dic_layer1[pnt_id][1])
                #pt2 = QgsPointXY(dic_layer2[pnt_id][0], dic_layer1[pnt_id][1])
                distance = d.measureLine(dic_layer1[pnt_id], dic_layer2[pnt_id])
                # fills result dictionary
                dic_result[id1_colname].append(pnt_id)
                dic_result[id2_colname].append(pnt_id)
                dic_result[dist_colname].append(distance)
            # if point is present only in one layer
            else:
                # fills result dictionary
                dic_result[dist_colname].append(NULL)
                if pnt_id in dic_layer1.keys():
                    dic_result[id1_colname].append(pnt_id)
                    dic_result[id2_colname].append(NULL)
                else:
                    dic_result[id1_colname].append(NULL)
                    dic_result[id2_colname].append(pnt_id)
        # convert dictionary to pandas dataframe
        df_result = pd.DataFrame.from_dict(dic_result)
        # finished
        return df_result
            
    
    # do some calculations on distances dataframe (round distances...)
    def dfCalculations(self, df, id1_colname, decimal_count, dist_colname, riverdist_colname, feedback):
        # 1/ round distances
        ###########################################
        # round column with straight line distances
        df[dist_colname] = df[dist_colname].apply(lambda x:round(float(x), decimal_count) if x != NULL else NULL)
        # round column with distances along river axis
        df[riverdist_colname] = df[riverdist_colname].apply(lambda x:round(float(x), decimal_count) if x != NULL else NULL)
        
        # 2/ sort lines by point id
        ###########################################
        #df = df.sort_values(by=[id1_colname], key=lambda x: np.argsort(index_natsorted(df[id1_colname])))
        
        return df
    
            
    # given a dataframe and the output table, write dataframe to table       
    def addFeaturestoTable(self, df, output_path):
        df.to_csv(output_path, index=False)  

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
