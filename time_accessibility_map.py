# This program creates geolocation data of time accessibility
# of cities from given origin city in Czechia
# Copyright (C) 2020  Filip Cizmar
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.

import argparse
import json
import lzma
import pickle
import sys
import time
import re

from datetime import datetime
from statistics import mean
from typing import List
from urllib.request import Request, urlopen
from urllib.parse import quote
from colour import Color
from geopy.geocoders import Nominatim
from bs4 import BeautifulSoup, Tag


class City:

	# Sets main information about the new city
	def __init__(self, name: str, district: str, population: int):
		self.name: str = name
		self.district: str = district
		self.population = population
		self.coordinates: List[float, float]

	def __eq__(self, other):
		return self.name == other.name

	def __str__(self):
		return self.name

	def _get_address_formatted(self) -> str:
		return self.name + ', ' + self.district + ', Czechia'

	# Uses OSM geolocator to get coordinates of a city
	# from given address
	def load_coordinates(self):
		geolocator = Nominatim(user_agent="time_accessibility_map")
		location = geolocator.geocode(self._get_address_formatted())
		self.coordinates = [location.longitude, location.latitude]


class Connection:

	# Vehicle type comes from connection search engine attributes
	# enum of 'vlaky', 'vlakyautobusy', ...
	def __init__(self, from_city: City, to_city: City,
				 veh_type: str = 'vlaky',
				 date_time: datetime = datetime(2020, 9, 15, 7, 0, 0)):

		self.from_city: City = from_city
		self.to_city: City = to_city
		self.veh_type: str = veh_type
		self.date_time: datetime = date_time

		self.connections: List[Tag] = []
		self.connections_times: List[int] = []
		self.connections_distances: List[int] = []
		self.distance: float = 0

		self.ratio_absolute: float

	# Loads connections from the IDOS engine
	# based on a connection instance
	def load_idos(self):

		if self.from_city == self.to_city:
			print('Cannot find connection to the same city.')
			return

		self.set_distance()
		soup: BeautifulSoup

		url = 'https://idos.idnes.cz/' + \
			  self.veh_type + '/spojeni/vysledky/?date=' + \
			  datetime.strftime(self.date_time, "%d.%m.%Y&time=%H:%M") + '&f=' + \
			  quote(self.from_city.name) + '&fc=1&t=' + \
			  quote(self.to_city.name) + '&tc=1'

		print('Getting connection for',
			  str(self.from_city), '--', str(self.to_city),
			  'URL: ', url)

		request = Request(url)
		webURL = urlopen(request)

		if 200 <= webURL.getcode() < 400:
			response_body = webURL.read()
			encoding = webURL.info().get_content_charset('utf-8')
			soup = BeautifulSoup(response_body.decode(encoding),
				features="html.parser")

		else:
			raise IOError('IDOS does not load for URL:', url)

		webURL.close()

		# Tries to find some connections in the resulted HTML
		try:
			# Regex to find exact connectons HTML elements
			connection_box_regex = re.compile('connectionBox-[0-9]+')
			self.connections = soup.find_all(id=connection_box_regex)

			if len(self.connections) == 0:
				raise IOError('Not enough connections')

			# If some connections found iterate them
			for connection in self.connections:

				# Tries to parse a connection
				# If it fails it keeps processing next connections
				try:

					# Parses time and distance HTML elements
					time = connection.div.div.label.p.strong.getText()
					distance = connection.div.div.label.p.find_all('strong')[1].getText()
					self.connections_distances.append(
						int(re.search(r'([0-9]+) km', distance).group(1)))

					# Makes ready for getting connection total number of seconds
					total_seconds = 0
					hours = re.search(r'([0-9]+) hod', time)
					minutes = re.search(r'([0-9]+) min', time)

					if bool(hours):
						total_seconds += int(hours.group(1)) * 60 * 60

					if bool(minutes):
						total_seconds += int(minutes.group(1)) * 60

					self.connections_times.append(total_seconds)

				except IndexError as e:
					print('Bad formatted connection box for stops:',
						  self.from_city.name, '--', self.to_city.name,
						  'for URL:', url)

			# Transforms soup tags to strings
			# Tags cannot be easily serialized
			self.connections = [str(con) for con in self.connections]

			# Data integrity check
			if len(self.connections) == 0 or \
					len(self.connections_times) == 0 or \
					len(self.connections_distances) == 0:
				return None

			return self

		except (IOError, IndexError) as e:
			print('Bad formatted HTML for stops:',
				  self.from_city.name, '--', self.to_city.name,
				  'for URL:', url)

	# Calculates distance between given coordinates
	# It follows the Earth shape
	# By default it uses self cities
	def set_distance(self, from_city: City = None, to_city: City = None):

		from_city = self.from_city if from_city is None else from_city
		to_city = self.to_city if to_city is None else to_city

		if len(to_city.coordinates) != 2 and len(from_city.coordinates) != 2:
			raise IndexError('City coordinates are not set')

		from math import sin, cos, sqrt, atan2, radians

		# approximate radius of earth in km
		R = 6373.0

		lat1 = radians(from_city.coordinates[1])
		lon1 = radians(from_city.coordinates[0])
		lat2 = radians(to_city.coordinates[1])
		lon2 = radians(to_city.coordinates[0])

		dlon = lon2 - lon1
		dlat = lat2 - lat1

		a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
		c = 2 * atan2(sqrt(a), sqrt(1 - a))

		distance = R * c

		self.distance = distance


class Cities:

	# Loads the html source file and parses it
	# local: path to the local source file or empty string
	def __init__(self, limit: int):

		self.cities: List[City] = []

		soup: BeautifulSoup

		# Reads the list of cities from the wiki article
		url = 'https://cs.wikipedia.org/wiki/Rejst' + quote('ř') + \
			  '%C3%ADk:' + quote('Seznam_měst_v_Česku_podle_počtu_obyvatel')

		request = Request(url)
		webURL = urlopen(request)

		# Checks the request response code
		if 200 <= webURL.getcode() < 400:
			response_body = webURL.read()
			encoding = webURL.info().get_content_charset('utf-8')
			soup = BeautifulSoup(response_body.decode(encoding),
								 features="html.parser")

		# Raises exception in case of a problem
		else:
			raise IOError('Wiki does not load.')

		webURL.close()

		# Finds all tr elements in the page
		# each tr element contains a single city
		trs = soup.find_all('tr')[1:]

		# Iterates all cities and extracts the data from the tr elements
		# up to the given limit
		# Name, District, Population
		for tr in trs[0:limit]:
			tds = tr.find_all('td')
			self.cities.append(City(
				tds[1].getText().rstrip(),
				tds[5].getText().rstrip(),
				int(re.sub(re.compile(r'\s+'), '', tds[3].getText().rstrip()))
			))

	# Sets coordinates to all cities
	def set_all_coordinates(self):
		print('Get all coordinates may take some time...')
		for city in self:
			if not hasattr(city, 'coordinates') or city.coordinates is None:
				city.load_coordinates()

	def get_city_by_name(self, name: str) -> City:
		for city in self:
			if city.name == name:
				return city

	# Iterates throw all cities in the local list
	def __iter__(self) -> City:
		for city in self.cities:
			yield city

	# Makes Cities class subscribable
	def __getitem__(self, item: int) -> City:
		return self.cities[item]

	def save(self, path):
		with lzma.open(path, "wb") as file:
			pickle.dump(self, file)


class Connections:

	# Loads all connections
	def __init__(self, cities: Cities, limit: int, origin: City, veh_type: str):

		self.connections: List[Connection] = []

		# Iterates city pairs to get their connections
		for city in cities[0:limit]:
			connection = Connection(origin, city, veh_type=veh_type)
			loaded_connection = connection.load_idos()

			# Filter bad responses
			if loaded_connection is not None:
				self.connections.append(loaded_connection)

			# Just to be inconspicuous to idos
			time.sleep(0.5)


	# Returns a GeoJson file of all cities and their time accessibility
	def get_geojson(self, limit: int, ratio_absolute: bool):

		max = 0
		min = float('inf')

		# Iterate all connections up to the given limit
		# Connections are ordered by the population of destination city
		for connection in self.connections[0:limit]:
			# if connection.to_city.name == 'Jílové u Prahy':
			# 	continue

			# If the ratio option set it uses the mean time divided by the distance
			# else the mean time
			# for choose a color of a city
			connection.ratio_absolute = \
				mean(connection.connections_times) / connection.distance \
					if ratio_absolute \
					else mean(connection.connections_times)

			# Simple max / min search
			max = connection.ratio_absolute \
				if connection.ratio_absolute > max else max
			min = connection.ratio_absolute \
				if connection.ratio_absolute < min else min

		# Inits the GeoJson structure
		geojson = {"type": "FeatureCollection", "features": []}

		# Iterates all connections up to the given limit
		for connection in self.connections[0:limit]:
			# if connection.to_city.name == 'Jílové u Prahy':
			# 	continue

			if limit > len(self.connections):
				limit = len(self.connections)

			# Choose a size of city icon depending on its population
			# It separates the city set right to the 3 thirds
			icon_size = "small"
			if connection.to_city.population > \
					self.connections[0:limit][((limit - 1) * 2) // 3].to_city.population:
				icon_size = "medium"
			if connection.to_city.population > \
					self.connections[0:limit][(limit - 1) // 3].to_city.population:
				icon_size = "large"

			# Normalized ratio or absolute value to 0--1 interval
			color_index = (connection.ratio_absolute - min) / (max - min)

			# Creates an appropriate color of a city
			# 0--0.3333 interval belongs to red--yellow--green
			color = Color(hsl=(0.3333 - 0.3333 * color_index, 1, 0.5))

			# Sets a feature attributes
			geojson['features'].append(
				{
					"type": "Feature",
					"properties": {
						"marker-size": icon_size,
						"marker-color": color.hex_l,
						"name": connection.to_city.name,
						"connections_times": connection.connections_times,
						"connections_distances": connection.connections_distances,
						"mean_time": mean(connection.connections_times),
						"distance": connection.distance,
						"connections_details": connection.connections,

					},
					"geometry": {
						"type": "Point",
						"coordinates":
							connection.to_city.coordinates
					}
				}
			)

		return geojson

	# Allows to easy append right to Connections class
	def append(self, other):
		self.connections.append(other)

	def save(self, path):
		with lzma.open(path, "wb") as file:
			pickle.dump(self, file)

	@staticmethod
	def load(path):
		with lzma.open(path, "rb") as file:
			return pickle.load(file)


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument("--local_cities", default='', type=str, help="Path to list of cities file.")
	parser.add_argument("--save_cities", default='', type=str, help="Save list of cities to given.")
	parser.add_argument("--local_connections", default='', type=str, help="Path to list of connections file.")
	parser.add_argument("--save_connections", default='', type=str, help="Save list of connections to given path.")
	parser.add_argument("--limit", default=20, type=int, help="Maximum number of cities exported to geojson output file ordered by population.")
	parser.add_argument("--origin", default='Praha', type=str, help="Origin city of all connections.")
	parser.add_argument("--vehicles_type", default='vlaky', type=str, help="'vlaky' for trains only, 'vlakyautobusy' for trains and buses.")
	parser.add_argument("--ratio", default=False, type=bool, help="Use time / distance ration to color the cities else pure time.")
	parser.add_argument("--save_output", default='./time_accessibility_map.geojson', type=str, help="Save output GeoJson file to given path.")
	parser.add_argument("--connections_only", default=True, type=bool, help="Skip cities and load connections file. The file path must be specified.")
	args = parser.parse_args([] if "__file__" not in globals() else None)

	connections: Connections
	cities: Cities
	origin: City

	if not args.connections_only or args.local_connections == '':

		if args.local_cities == '':
			cities = Cities(args.limit)
			cities.set_all_coordinates()

		else:
			# Connection load function loads any object
			cities = Connections.load(args.local_cities)

		origin = cities.get_city_by_name(args.origin)

		if args.save_cities != '':
			cities.save(args.save_cities)

		if args.local_connections != '':
			connections = Connections.load(args.local_connections)
		else:
			connections = Connections(cities, args.limit, origin, args.vehicles_type)

	else: # args.local_connections != '':
		connections = Connections.load(args.local_connections)

	# Saves connections
	if args.save_connections != '':
		connections.save(args.save_connections)

	geojson_out = connections.get_geojson(args.limit, args.ratio)

	# If output option specified saves to given path
	if args.save_output != '':
		try:
			with open(args.save_output, 'w+') as f:
				f.seek(0)
				f.write(json.dumps(geojson_out))
				print('GeoJson output file saved.')

		except IOError as e:
			print("Write file has failed.")
