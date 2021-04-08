# River Tools QGIS processing plugin : collection of tools for studying rivers

## Brief summary

This is a processing plugin for QGIS. It has several tools which can be used to study rivers :

-  segmentation boxes : divides a long polygon, for example a river polygon, into multiple boxes of a given length and width.
- distance along river : distances between pair of points along a river axis (points are projected on this axis)

## Detailed description of algorithms :

### Segmentation boxes

This plugin divides a river into multiple with same length :

illustration goes here !



### Input data :

* a river layer, which can be polygon or line
* an optional line layer for the river centerline, which will be used if river layer is polygon. If river layer is polygon and no centerline is set, it will be calculated
* the length of the boxes to be created, same units as river layer
* the width of the boxes to be created : will only be used if river layer is a line layer, otherwise width will be that of the river

### Ouput data :

* polygon layer with boxes
* optionally, river centerline layer

### How it works

There are 3 steps for this plugin :

- creating the polygon centerline, with grass "v.voronoi.skeleton" algorithm, if input layer is set and no centerline provided
- creating points along this centerline at a given interval, using QGIS algorithm "points along line"
- creating Thiessen polygons for this point layer, using QGIS algorithm "Voronoi polygons"
- clipping these polygons by the initial polygon layer, using QGIS algorithm "Clip" if input layer is polygon, or by a buffer of given width if input layer is line

## Distance along river



