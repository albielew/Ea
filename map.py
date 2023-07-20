from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from PIL import Image

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

# Update the path to the Chrome driver according to your system
driver_path = '/usr/bin/chromedriver'
service = Service(driver_path)

# Set the options for the Chrome driver
driver = webdriver.Chrome(service=service, options=options)
driver.set_window_size(530, 445)
driver.implicitly_wait(1)

url = "https://embed.windy.com/embed2.html?lat=53.514&lon=-2.944&detailLat=53.300&detailLon=-2.100&width=530&height=490&zoom=4&level=surface&overlay=wind&product=ecmwf&menu=&message=true&marker=&calendar=now&pressure=true&type=map&location=coordinates&detail=&metricWind=mph&metricTemp=%C2%B0C&radarRange=-1"
driver.get(url)
driver.save_screenshot('weather.png')

basewidth = 530
img = Image.open('weather.png')
driver.quit()

wpercent = (basewidth / float(img.size[0]))
hsize = int((float(img.size[1]) * float(wpercent)))
img = img.resize((basewidth, hsize), Image.ANTIALIAS)
img.save('/home/pi/images/weather_icons/kia.bmp')
