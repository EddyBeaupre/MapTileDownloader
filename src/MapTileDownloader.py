#!/usr/bin/env python3
"""
MapTileDownloader
This module provides functionality to download map tiles from a specified URL and stitch them together to form a larger map image. It includes a command-line interface for specifying the map region, zoom level, and output filename.
Classes:
    MapTileDownloader: A class to download and stitch map tiles from a specified URL.
Functions:
    main(): The main function that parses command-line arguments and initiates the map tile download process.
Usage:
    Run this script from the command line with the required arguments to download a map region and save it as an image file.
Example:
    python MapTileDownloader.py "50.048426,-66.813065" "50.024210,-66.763433" -z 14 -u "https://mt.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
Dependencies:
    - argparse
    - sys
    - os
    - re
    - threading
    - datetime
    - cv2 (OpenCV)
    - numpy
    - requests
    - progressbar
Note:
    Ensure that the required dependencies are installed before running the script. You can install them using pip:
    pip install opencv-python numpy requests progressbar2
"""
__version__ = '1.1.0'
__author__ = 'Eddy Beaupré (https://github.com/EddyBeaupre)'
__license__ = 'MIT'

# -*- coding: utf-8 -*-


import argparse
import sys
import os
import re
import threading
from datetime import datetime
try:
    import cv2
except ImportError as e:
    print("Error: OpenCV not found. Please install it using 'pip install opencv-python'")
    sys.exit(1)
try:
    import numpy as np
except ImportError as e:
    print("Error: numpy not found. Please install it using 'pip install numpy'")
    sys.exit(1)
try:
    import requests
except ImportError as e:
    print("Error: requests not found. Please install it using 'pip install requests'")
    sys.exit(1)
try:
    import progressbar
except ImportError as e:
    print("Error: progressbar not found. Please install it using 'pip install progressbar2'")
    sys.exit(1)

class MapTileDownloader:
    def __init__(self, url: str, headers: dict[str, str] = None):
        """
        Initializes the MapTileDownloader with the specified URL and optional headers.

        Args:
            url (str): The URL to download the map tile from.
            headers (dict[str, str], optional): A dictionary of HTTP headers to include in the request. 
                                                If not provided, a default set of headers will be used.

        Attributes:
            url (str): The URL to download the map tile from.
            headers (dict[str, str]): A dictionary of HTTP headers to include in the request.

        This function initializes the MapTileDownloader with the specified URL and optional headers.
        """

        self.url = url
        self.headers = {
            'cache-control': 'max-age=0',
            'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="99", "Google Chrome";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.82 Safari/537.36'
        } if headers is None else headers

    def get_image_info(self, tx: int, ty: int, zoom: int) -> tuple[int, int, int]:
        """
        Retrieves information about a specific map tile at a given zoom level.

        Args:
            tx (int): The x-coordinate of the tile.
            ty (int): The y-coordinate of the tile.
            zoom (int): The zoom level of the tile.

        Returns:
            tuple[int, int, int]: A tuple containing the width, height, and number of channels of the tile.

        This function sends a GET request to the specified URL with the tile coordinates and zoom level, 
        retrieves the tile image, decodes it, and returns the width, height, and number of channels of
        the tile image. If the tile is not found, it returns the default size of 256x256 with 1 channel.
        """

        response = requests.get(self.url.format(x=tx, y=ty, z=zoom), headers=self.headers)
        arr = np.asarray(bytearray(response.content), dtype=np.uint8)
        tile = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)

        if tile is not None:
            height, width = tile.shape[:2]
            channels = tile.shape[2] if len(tile.shape) > 2 else 1
        else:
            width, height, channels = 256, 256, 1

        return width, height, channels

    def download_map_region(self, lat1: float, lon1: float, lat2: float, lon2: float, zoom: int, filename: str):
        """
        Downloads a map region defined by latitude and longitude coordinates and saves it as an image file.

        Args:
            lat1 (float): Latitude of the top-left corner.
            lon1 (float): Longitude of the top-left corner.
            lat2 (float): Latitude of the bottom-right corner.
            lon2 (float): Longitude of the bottom-right corner.
            zoom (int): Zoom level for the map tiles.
            filename (str): The filename to save the downloaded image.

        Returns:
            None

        This function downloads map tiles from the specified URL and stitches them together to form a single image.
        It converts latitude and longitude coordinates to tile coordinates using the Web Mercator projection,
        calculates the pixel coordinates and tile coordinates of the corners, and determines the image size and number of channels.
        The function then downloads and places each tile into the appropriate position in the larger image,
        handling the placement and cropping of border tiles to ensure they fit correctly within the image boundaries.
        Finally, the stitched image is saved to the specified filename.
        """

        def lat_lon_to_tile_coords(lat, lon, scale) -> tuple[float, float]:
            """
            Converts latitude and longitude to tile coordinates.

            Args:
                lat (float): Latitude in degrees.
                lon (float): Longitude in degrees.
                scale (float): Scale factor for the tile coordinates.

            Returns:
                tuple[float, float]: The x and y tile coordinates.

            This function converts latitude and longitude coordinates to tile coordinates using the Web Mercator projection.
            It scales the coordinates by the specified factor and returns the x and y tile coordinates.
            """

            siny = np.sin(lat * np.pi / 180)
            siny = min(max(siny, -0.9999), 0.9999)
            x = scale * (0.5 + lon / 360)
            y = scale * (0.5 - np.log((1 + siny) / (1 - siny)) / (4 * np.pi))
            return x, y

        scale = 1 << zoom

        # Find the pixel coordinates and tile coordinates of the corners
        tl_proj_x, tl_proj_y = lat_lon_to_tile_coords(lat1, lon1, scale)
        br_proj_x, br_proj_y = lat_lon_to_tile_coords(lat2, lon2, scale)

        # Find the tile size and number of channels
        tile_size_x, tile_size_y, tile_channels = self.get_image_info(int(tl_proj_x), int(tl_proj_y), zoom)

        tl_pixel_x = int(tl_proj_x * tile_size_x)
        tl_pixel_y = int(tl_proj_y * tile_size_y)
        br_pixel_x = int(br_proj_x * tile_size_x)
        br_pixel_y = int(br_proj_y * tile_size_y)

        tl_tile_x = int(tl_proj_x)
        tl_tile_y = int(tl_proj_y)
        br_tile_x = int(br_proj_x)
        br_tile_y = int(br_proj_y)

        img_w = abs(tl_pixel_x - br_pixel_x)
        img_h = br_pixel_y - tl_pixel_y

        self.tiles_total = (br_tile_x - tl_tile_x + 1) * (br_tile_y - tl_tile_y + 1)
        self.tiles_current = 0

        self.bar = progressbar.ProgressBar(maxval=self.tiles_total)

        print(f'       Tiles server: {self.url}')
        print(f'    Top-left corner: {lat1:.6f}, {lon1:.6f}')
        print(f'Bottom-right corner: {lat2:.6f}, {lon2:.6f}')
        print(f'         Zoom level: {zoom}')
        print(f'         Image size: {img_w}x{img_h}px ({br_tile_x - tl_tile_x + 1}x{br_tile_y - tl_tile_y + 1} tiles)')
        print(f'                     {br_tile_x - tl_tile_x + 1}x{br_tile_y - tl_tile_y + 1} tiles')
        print(f'                     {tile_size_x}x{tile_size_y}px per tiles')
        print(f'     Color channels: {tile_channels}')
        print(f'    Output filename: {filename}')

        img = np.zeros((img_h, img_w, tile_channels), dtype=np.uint8)

        def build_row(tile_y: int):
            """
            Downloads and places a row of image tiles into a larger image.

            Args:
                tile_y (int): The y-coordinate of the tile row to be downloaded.

            Returns:
                None

            This function iterates over the x-coordinates of the tiles within the specified range,
            downloads each tile, decodes it, and places it into the appropriate position in the
            larger image. It handles the placement and cropping of border tiles to ensure they
            fit correctly within the image boundaries.
            """

            for tile_x in range(tl_tile_x, br_tile_x + 1):
                response = requests.get(self.url.format(x=tile_x, y=tile_y, z=zoom), headers=self.headers)
                arr = np.asarray(bytearray(response.content), dtype=np.uint8)
                tile = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)

                if tile is not None:
                    # Find the pixel coordinates of the new tile relative to the image
                    tl_rel_x = tile_x * tile_size_x - tl_pixel_x
                    tl_rel_y = tile_y * tile_size_y - tl_pixel_y
                    br_rel_x = tl_rel_x + tile_size_x
                    br_rel_y = tl_rel_y + tile_size_y

                    # Define where the tile will be placed on the image
                    img_x_l = max(0, tl_rel_x)
                    img_x_r = min(img_w + 1, br_rel_x)
                    img_y_l = max(0, tl_rel_y)
                    img_y_r = min(img_h + 1, br_rel_y)

                    # Define how border tiles will be cropped
                    cr_x_l = max(0, -tl_rel_x)
                    cr_x_r = tile_size_x + min(0, img_w - br_rel_x)
                    cr_y_l = max(0, -tl_rel_y)
                    cr_y_r = tile_size_y + min(0, img_h - br_rel_y)

                    self.tiles_current += 1

                    self.bar.update(self.tiles_current)

                    img[img_y_l:img_y_r, img_x_l:img_x_r] = tile[cr_y_l:cr_y_r, cr_x_l:cr_x_r]

        print('\nDownloading map tiles...')
        self.bar.start()
        threads = []
        for tile_y in range(tl_tile_y, br_tile_y + 1):
            thread = threading.Thread(target=build_row, args=[tile_y])
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()
        self.bar.finish()

        print(f'Saving image as \'{filename}\'... ', end='')
        try:
            cv2.imwrite(filename, img)
        except Exception as e:
            print(f'Error:\n{e}')
            return
        print('Done.')

def main():
    try:
        parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description='Download map images from Google Maps or other tile servers.', epilog="Copyright (c) 2022 andolg (https://github.com/andolg)\nCopyright (c) 2024 Eddy Beaupré (https://github.com/EddyBeaupre)")
        parser.add_argument('top_left', action="store", type=str, help="Top-left corner of the map region (example: 50.048426,-66.813065)")
        parser.add_argument('bot_right', action="store", type=str, help="Bottom-right corner of the map region (example: 50.024210,-66.763433)")
        parser.add_argument('file', nargs='?', action="store", type=str, help=f"Filename for the downloaded map (default: {os.path.join(os.getcwd(), 'img_<TIMESTAMP>.png')})", default=os.path.join(os.getcwd(), f'img_{datetime.now().strftime("%Y%m%d%H%M%S")}.png'))
        parser.add_argument('-z', '--zoom', action="store", help="Zoom level for the map tiles (default: 14)", default=14)
        parser.add_argument('-u', '--url', action="store", type=str, help="tile URL service (default: https://mt.google.com/vt/lyrs=s&x={x}&y={y}&z={z})", default='https://mt.google.com/vt/lyrs=s&x={x}&y={y}&z={z}')
        parser.add_argument('--version', action='version', version='%(prog)s {version}'.format(version=__version__))
    
        def lat_long(data: str) -> tuple[float, float]:
            lat, lon = re.findall(r'[+-]?\d*\.\d+|d+', data)
            return float(lat), float(lon)

        args = parser.parse_args()
        map_tile_downloader = MapTileDownloader(args.url)
        lat1, lon1 = lat_long(args.top_left)
        lat2, lon2 = lat_long(args.bot_right)

        map_tile_downloader.download_map_region(lat1, lon1, lat2, lon2, int(args.zoom), os.path.abspath(args.file))
        return 0
    except Exception as e:
        print(f'Error: {e}')
        return 1

if __name__ == "__main__":
    sys.exit(main())
