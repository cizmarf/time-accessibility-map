# Time Accessibility Map

This project creates geolocation data of time accessibility of cities from given origin city in Czechia.

The main goal of this project is to show how long time it takes to get to all cities in Czechia from any different city. The attached visualizations files are created with the origin city set to Prague. 

The created data can be easily visualized by any GeoJson visualization tool.

The list of all cities comes from [Wiki](https://cs.wikipedia.org/wiki/Rejstř%C3%ADk:Seznam_měst_v_Česku_podle_počtu_obyvatel).

The connections search is powered by [IDOS](https://idos.idnes.cz/vlakyautobusy/spojeni/) engine. The local very favorite public transport connections search tool.

## Code Overview 

The source code is written in Python 3 language.

This code uses a few external libraries especially BeautifulSoup for HTML parsing and GeoPy for geographic work.

The flow of the code depends on many options. But the general initial run should download the Wiki page and extract all cities, create all connections from a origin city to all different cities, save the output GeoJson file.

To get all connections needs to be done one by one from IDOS engine. It means it generates hundreds requests and it can overload this service and possibly it can ban local IP. Because the program scrapes this web page the right results strongly depend on its version and HTML style it may need to change the source code in the future.

Because the program uses the network a lot it can make it very slow. But the main class instances can be saved for future reuse. The proper options needs to be set for it. Run `--help` for help.

## Results

The result of this project are created maps or data files bellow. Those maps include 280 biggest cities in Czechia. And they show time accessibility of them from Prague by green to red color fade. Green means less time needed or better accessibility, red means the opposite.

The all connections are searched for Sep. 15 2020, 7 AM Prague time and the most of them consist of 3 different connections as they are returned from IDOS engine. 

Those maps can be separated by visualized data. The first group shows the mean of the pure time duration of the found connections. It is easy to see that the travel time is increasing by the distance from Prague. The second group shows the mean of the travel times divided by geographical distance. In other words it penalizes the travel time by the distance so the cities far away can be green if you can get there fast. But the cities closer to Prague can be red if there is no direct or fast connection.

The other separation depends on vehicles types: train only or train and bus. In comparison of these types it is easy to see that some regions are not accessible by trains but they are operated by buses well.

### Conclusion

There are 4 maps:

- [Trains connections absolute time.](./time_accessibility_map_train-absolute-280.geojson)

- [Trains connections relative to distance.](./time_accessibility_map_train-ratio-280.geojson)

- [Trains and buses connections absolute time.](./time_accessibility_map_bus_train-absolute-280.geojson)

- [Trains and buses connections relative to distance.](./time_accessibility_map_bus_train-ratio-280.geojson)

Because the absolute time maps show that the travel time is increasing by distance which is obvious they are not so interesting.

On the other hand the relative time maps show all regions with very good accessibility by green color. It is easy to see the main train corridor from Prague to Moravia. But almost all the cities in Bohemia are badly accessible even if they are close to Prague by their distance.
