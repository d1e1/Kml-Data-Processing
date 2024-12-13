import os
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement, tostring, ElementTree
from geopy.distance import geodesic
from datetime import datetime

class KMLAutomationTool:
    def __init__(self, input_file, output_file, report_file):
        self.input_file = input_file
        self.output_file = output_file
        self.report_file = report_file
        self.namespace = {'kml': 'http://www.opengis.net/kml/2.2'}
        self.tree = ET.parse(input_file)
        self.root = self.tree.getroot()

    def parse_and_filter_data(self):
        filtered_data = []
        for placemark in self.root.findall('.//kml:Placemark', self.namespace):
            name = placemark.find('kml:name', self.namespace)
            description = placemark.find('kml:description', self.namespace)
            time_span = placemark.find('kml:TimeSpan', self.namespace)
            coordinates = placemark.find('.//kml:coordinates', self.namespace)

            if description is not None and "Projecting" in description.text:
                continue

            start_time, end_time, date = None, None, None
            if name is not None and '-' in name.text:
                parts = name.text.split('-')
                start_time = parts[0]
                end_time = parts[1]
                date = start_time[:8]  # Extract date from start_time

            placemark_data = {
                'name': name.text if name is not None else None,
                'description': description.text if description is not None else None,
                'date': date,
                'start_time': start_time,
                'end_time': end_time,
                'coordinates': coordinates.text.strip() if coordinates is not None else None,
            }
            filtered_data.append(placemark_data)
        return filtered_data

    def organize_data_by_date(self, data):
        organized_data = {}
        for entry in data:
            date = entry.get('date')
            if date:
                if date not in organized_data:
                    organized_data[date] = []
                organized_data[date].append(entry)
        return organized_data

    def calculate_distance(self, coordinates):
        if not coordinates:
            return 0.0

        points = [tuple(map(float, coord.split(",")[:2])) for coord in coordinates.split()]
        total_distance = sum(geodesic(points[i], points[i+1]).kilometers for i in range(len(points) - 1))
        return total_distance

    def calculate_time_difference(self, start_time, end_time):
        if not start_time or not end_time:
            return None
        try:
            start = datetime.strptime(start_time, "%Y%m%d%H%M%S")
            end = datetime.strptime(end_time, "%Y%m%d%H%M%S")
            return (end - start).total_seconds() / 3600.0  # Time in hours
        except ValueError:
            return None

    def calculate_path_density(self, coordinates):
        if not coordinates:
            return None
        points = [tuple(map(float, coord.split(",")[:2])) for coord in coordinates.split()]
        lats, lons = zip(*points)
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        bounding_box_area = (max_lat - min_lat) * (max_lon - min_lon)
        total_distance = self.calculate_distance(coordinates)
        return total_distance / bounding_box_area if bounding_box_area > 0 else None

    def generate_report(self, organized_data):
        with open(self.report_file, 'w') as report:
            report.write("Date,Total Distance (km),Placemark Count,Total Time (hrs),Average Speed (km/h),Path Density,Max Segment Distance (km),Min Segment Distance (km)\n")
            for date, placemarks in organized_data.items():
                total_distance = 0.0
                total_time = 0.0
                path_densities = []
                max_segment = 0.0
                min_segment = float('inf')
                for placemark in placemarks:
                    coordinates = placemark['coordinates']
                    distance = self.calculate_distance(coordinates)
                    total_distance += distance

                    time_diff = self.calculate_time_difference(placemark['start_time'], placemark['end_time'])
                    if time_diff:
                        total_time += time_diff

                    density = self.calculate_path_density(coordinates)
                    if density:
                        path_densities.append(density)

                    # Calculate segment distances
                    points = [tuple(map(float, coord.split(",")[:2])) for coord in coordinates.split()] if coordinates else []
                    for i in range(len(points) - 1):
                        segment_distance = geodesic(points[i], points[i+1]).kilometers
                        max_segment = max(max_segment, segment_distance)
                        min_segment = min(min_segment, segment_distance)

                avg_speed = total_distance / total_time if total_time > 0 else 0
                avg_density = sum(path_densities) / len(path_densities) if path_densities else 0
                min_segment = min_segment if min_segment != float('inf') else 0

                report.write(f"{date},{total_distance:.2f},{len(placemarks)},{total_time:.2f},{avg_speed:.2f},{avg_density:.2f},{max_segment:.2f},{min_segment:.2f}\n")

    def create_new_kml(self, organized_data):
        kml = Element('kml', xmlns="http://www.opengis.net/kml/2.2")
        document = SubElement(kml, 'Document')

        
        style = SubElement(document, 'Style', id="greenLineStyle")
        line_style = SubElement(style, 'LineStyle')
        color = SubElement(line_style, 'color')
        color.text = "ff00ff00"  
        width = SubElement(line_style, 'width')
        width.text = "2"

        for date, placemarks in organized_data.items():
            folder = SubElement(document, 'Folder')
            folder_name = SubElement(folder, 'name')
            folder_name.text = date

            for placemark in placemarks:
                pm = SubElement(folder, 'Placemark')

                if placemark['name']:
                    name = SubElement(pm, 'name')
                    name.text = placemark['name']

                if placemark['description']:
                    description = SubElement(pm, 'description')
                    description.text = placemark['description']

                if placemark['start_time'] or placemark['end_time']:
                    extended_data = SubElement(pm, 'ExtendedData')

                    if placemark['start_time']:
                        data_start = SubElement(extended_data, 'Data', name="start_time")
                        value_start = SubElement(data_start, 'value')
                        value_start.text = placemark['start_time']

                    if placemark['end_time']:
                        data_end = SubElement(extended_data, 'Data', name="end_time")
                        value_end = SubElement(data_end, 'value')
                        value_end.text = placemark['end_time']

                if placemark['coordinates']:
                    style_url = SubElement(pm, 'styleUrl')
                    style_url.text = "#greenLineStyle"

                    line_string = SubElement(pm, 'LineString')
                    coordinates = SubElement(line_string, 'coordinates')
                    coordinates.text = placemark['coordinates']

        tree = ElementTree(kml)
        tree.write(self.output_file, encoding='utf-8', xml_declaration=True)

    def run(self):
        print("Parsing and filtering data...")
        filtered_data = self.parse_and_filter_data()
        print(f"Filtered {len(filtered_data)} placemarks.")

        print("Organizing data by date...")
        organized_data = self.organize_data_by_date(filtered_data)

        print("Creating new KML file...")
        self.create_new_kml(organized_data)
        print(f"Output saved to {self.output_file}")

        print("Generating report...")
        self.generate_report(organized_data)
        print(f"Report saved to {self.report_file}")

# File paths
input_file_path = 'Al-Malqa-2024-10-17_to_23.kml'
output_file_path = 'Filtered_Organized_Al-Malqa.kml'
report_file_path = 'Al-Malqa_Report.csv'

tool = KMLAutomationTool(input_file_path, output_file_path, report_file_path)
tool.run()
