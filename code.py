import os, time, gc, math
import board, displayio, terminalio
import adafruit_display_text.label
import neopixel
from adafruit_matrixportal.matrixportal import MatrixPortal
from microcontroller import watchdog as w
from watchdog import WatchDogMode
import wifi, socketpool, ssl, adafruit_requests

w.timeout = 60
w.mode = WatchDogMode.RESET

def wfeed():
    try: w.feed()
    except: pass

FONT = terminalio.FONT

try:
    from secrets import secrets
except ImportError:
    raise

QUERY_DELAY    = 30
BOUNDS_BOX     = secrets["bounds_box"]

# Feature flags
ENABLE_FLIGHTS  = secrets.get("enable_flights",  True)
ENABLE_WEATHER  = secrets.get("enable_weather",  True)
ENABLE_FOOTBALL = secrets.get("enable_football", True)
ENABLE_CRICKET  = secrets.get("enable_cricket",  True)
HOME_AIRPORT   = secrets["home_airport"]
FOOTBALL_KEY   = secrets.get("football_key", "")

# Colours
ROW_ONE_COLOUR   = 0xEE82EE
ROW_TWO_COLOUR   = 0x4B0082
ROW_THREE_COLOUR = 0xFFA500
PLANE_COLOUR     = 0x4B0082
TEXT_SPEED       = 0.04
FLAP_SPEED       = 0.03
FLAP_CHARS       = ' ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.'

# URLs
FLIGHT_URL  = "https://data-cloud.flightradar24.com/zones/fcgi/feed.js?bounds=" + BOUNDS_BOX + "&faa=1&satellite=1&mlat=1&flarm=1&adsb=1&gnd=0&air=1&vehicles=0&estimated=0&maxage=14400&gliders=0&stats=0&ems=1&limit=1"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast?latitude=47.3769&longitude=8.5417&current_weather=true&daily=sunrise,sunset&timezone=Europe%2FZurich&forecast_days=1"
FOOTBALL_BASE  = "https://api.football-data.org/v4/competitions/"
ESPN_BASE      = "https://site.api.espn.com/apis/site/v2/sports/soccer/"
SOFASCORE_LIVE = "https://api.sofascore.com/api/v1/sport/football/events/live"
# Cricinfo unofficial API - no key needed
CRICINFO_BASE    = "https://hs-consumer-api.espncricinfo.com/v1/pages"
CRICINFO_HEADERS = {
    "User-Agent": "ESPNCricinfo/8.0.0 CFNetwork/1399 Darwin/22.1.0",
    "Accept": "application/json",
    "Accept-Language": "en-GB,en;q=0.9",
}

# ESPN league slugs
ESPN_LEAGUES = {
    "PL":  "eng.1",
    "CL":  "uefa.champions",
    "EL":  "uefa.europa",
    "WC":  "fifa.world",
    "EC":  "uefa.euro",
    "IT1": "ita.1",
    "ES1": "esp.1",
    "FR1": "fra.1",
    "D1":  "ger.1",
}

ESPN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
    "Accept": "application/json",
    "Referer": "https://www.espn.com/",
}

SOFASCORE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}
HEXDB_URL = "https://hexdb.io/api/v1/aircraft/"
ADSB_URL  = "https://api.adsb.lol/v2/hex/"

rheaders = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0",
    "cache-control": "no-store, no-cache, must-revalidate, post-check=0, pre-check=0",
    "Accept": "application/json"
}

FOOTBALL_HEADERS = {"X-Auth-Token": FOOTBALL_KEY, "User-Agent": "Mozilla/5.0"} if FOOTBALL_KEY else {"User-Agent": "Mozilla/5.0"}

# ---- WiFi ----
def connect_wifi():
    ssid = os.getenv("CIRCUITPY_WIFI_SSID")
    pwd  = os.getenv("CIRCUITPY_WIFI_PASSWORD")
    for attempt in range(5):
        try:
            print("WiFi connect attempt "+str(attempt+1)+"...")
            wfeed()
            wifi.radio.connect(ssid, pwd)
            print("Connected to "+ssid)
            return True
        except Exception as e:
            print("WiFi failed: "+str(e))
            wfeed()
            time.sleep(3)
    return False

def checkConnection():
    if wifi.radio.ipv4_address:
        return True
    return connect_wifi()

connect_wifi()

def setup_requests():
    pool = socketpool.SocketPool(wifi.radio)
    return adafruit_requests.Session(pool, ssl.create_default_context())

requests_session = setup_requests()

# ---- Lookups ----
GA_TYPES = {'C172','C182','C208','PC12','TBM9','SR22','SR20','DA40','DA42',
            'PA28','PA46','E55P','C525','C550','C56X','C680','C750','GL5T','GLEX'}
GA_COLOUR         = 0x00FF00
COMMERCIAL_COLOUR = 0xEE82EE

AIRLINE_INFO = {
    'SWR':('Swiss Air',0xFF0000),'OAW':('Swiss Air',0xFF0000),
    'DLH':('Lufthansa',0xFFCC00),'BAW':('British Airw',0x003399),
    'EZY':('easyJet',0xFF6600),'RYR':('Ryanair',0x003399),
    'AFR':('Air France',0x002395),'KLM':('KLM',0x00A1DE),
    'UAE':('Emirates',0xCC0000),'THY':('Turkish',0xCC0000),
    'AUA':('Austrian',0xCC0000),'VLG':('Vueling',0xFF6600),
    'IBE':('Iberia',0xFF6600),'EWG':('Eurowings',0xFF6600),
    'EDW':('Edelweiss',0x00AAFF),'TAP':('TAP',0x00AA44),
    'SAS':('SAS',0x003399),'LOT':('LOT Polish',0x003399),
    'WZZ':('Wizz Air',0xC8007A),'TOM':('TUI',0x00539B),
    'CFG':('Condor',0xFFCC00),'TRA':('Transavia',0x00A650),
    'SXS':('SunExpress',0xFF6600),'BTI':('airBaltic',0x006400),
    'BOM':('Helvetic',0xCC0000),'QTR':('Qatar',0x6C1D45),
    'SIA':('Singapore',0xCC0000),'AAL':('American',0xCC0000),
    'UAL':('United',0x002395),'DAL':('Delta',0xCC0000),
    'ETH':('Ethiopian',0x007A4D),'TVS':('Smartwings',0xFF6600),
}

AIRPORT_INFO = {
    'ZRH':('Zurich','CH'),'GVA':('Geneva','CH'),'BSL':('Basel','CH'),
    'LHR':('Heathrow','GB'),'LGW':('Gatwick','GB'),'LCY':('City','GB'),
    'STN':('Stansted','GB'),'LTN':('Luton','GB'),'MAN':('Manchester','GB'),
    'EDI':('Edinburgh','GB'),'GLA':('Glasgow','GB'),'BHX':('Birmingham','GB'),
    'BRS':('Bristol','GB'),'NCL':('Newcastle','GB'),
    'FRA':('Frankfurt','DE'),'MUC':('Munich','DE'),'BER':('Berlin','DE'),
    'DUS':('Dusseldorf','DE'),'HAM':('Hamburg','DE'),'STR':('Stuttgart','DE'),
    'CGN':('Cologne','DE'),'NUE':('Nuremberg','DE'),
    'CDG':('De Gaulle','FR'),'ORY':('Orly','FR'),'NCE':('Nice','FR'),
    'LYS':('Lyon','FR'),'MRS':('Marseille','FR'),'TLS':('Toulouse','FR'),
    'BOD':('Bordeaux','FR'),'NTE':('Nantes','FR'),'LBG':('Le Bourget','FR'),
    'AMS':('Amsterdam','NL'),'EIN':('Eindhoven','NL'),
    'MAD':('Madrid','ES'),'BCN':('Barcelona','ES'),'PMI':('Palma','ES'),
    'AGP':('Malaga','ES'),'TFS':('Tenerife S','ES'),'LPA':('Gran Canaria','ES'),
    'ALC':('Alicante','ES'),'VLC':('Valencia','ES'),'IBZ':('Ibiza','ES'),
    'ACE':('Lanzarote','ES'),'FUE':('Fuerteventura','ES'),
    'FCO':('Rome','IT'),'MXP':('Milan Malpensa','IT'),'LIN':('Milan Linate','IT'),
    'VCE':('Venice','IT'),'NAP':('Naples','IT'),'PMO':('Palermo','IT'),
    'CTA':('Catania','IT'),'BLQ':('Bologna','IT'),'FLR':('Florence','IT'),
    'BGY':('Bergamo','IT'),'PSA':('Pisa','IT'),'VRN':('Verona','IT'),
    'LIS':('Lisbon','PT'),'OPO':('Porto','PT'),'FAO':('Faro','PT'),
    'FNC':('Funchal','PT'),
    'VIE':('Vienna','AT'),'GRZ':('Graz','AT'),'INN':('Innsbruck','AT'),'SZG':('Salzburg','AT'),
    'BRU':('Brussels','BE'),'CRL':('Charleroi','BE'),
    'CPH':('Copenhagen','DK'),'OSL':('Oslo','NO'),'ARN':('Stockholm','SE'),
    'GOT':('Gothenburg','SE'),'HEL':('Helsinki','FI'),
    'WAW':('Warsaw','PL'),'KRK':('Krakow','PL'),'GDN':('Gdansk','PL'),
    'PRG':('Prague','CZ'),'BTS':('Bratislava','SK'),'BUD':('Budapest','HU'),
    'ATH':('Athens','GR'),'HER':('Heraklion','GR'),'RHO':('Rhodes','GR'),
    'SKG':('Thessaloniki','GR'),'CFU':('Corfu','GR'),'JTR':('Santorini','GR'),
    'IST':('Istanbul','TR'),'SAW':('Sabiha','TR'),'AYT':('Antalya','TR'),
    'ADB':('Izmir','TR'),'DLM':('Dalaman','TR'),'BJV':('Bodrum','TR'),
    'DXB':('Dubai','AE'),'AUH':('Abu Dhabi','AE'),'DOH':('Doha','QA'),
    'TLV':('Tel Aviv','IL'),'AMM':('Amman','JO'),'BEY':('Beirut','LB'),
    'CAI':('Cairo','EG'),'RUH':('Riyadh','SA'),'JED':('Jeddah','SA'),
    'JFK':('New York JFK','US'),'LAX':('Los Angeles','US'),'MIA':('Miami','US'),
    'ORD':('Chicago','US'),'ATL':('Atlanta','US'),'SFO':('San Francisco','US'),
    'BOS':('Boston','US'),'DFW':('Dallas','US'),'EWR':('Newark','US'),
    'IAD':('Washington','US'),'SEA':('Seattle','US'),'DEN':('Denver','US'),
    'LAS':('Las Vegas','US'),'MCO':('Orlando','US'),
    'YYZ':('Toronto','CA'),'YVR':('Vancouver','CA'),'YUL':('Montreal','CA'),
    'NRT':('Tokyo Narita','JP'),'HND':('Tokyo Haneda','JP'),'KIX':('Osaka','JP'),
    'ICN':('Seoul','KR'),'HKG':('Hong Kong','HK'),'SIN':('Singapore','SG'),
    'BKK':('Bangkok','TH'),'HKT':('Phuket','TH'),
    'DEL':('Delhi','IN'),'BOM':('Mumbai','IN'),'BLR':('Bangalore','IN'),
    'PEK':('Beijing','CN'),'PVG':('Shanghai','CN'),
    'KUL':('Kuala Lumpur','MY'),'CGK':('Jakarta','ID'),'DPS':('Bali','ID'),
    'SYD':('Sydney','AU'),'MEL':('Melbourne','AU'),'BNE':('Brisbane','AU'),
    'AKL':('Auckland','NZ'),
    'JNB':('Johannesburg','ZA'),'CPT':('Cape Town','ZA'),
    'NBO':('Nairobi','KE'),'ADD':('Addis Ababa','ET'),
    'CMN':('Casablanca','MA'),'RAK':('Marrakech','MA'),
    'GRU':('Sao Paulo','BR'),'EZE':('Buenos Aires','AR'),'SCL':('Santiago','CL'),
    'BOG':('Bogota','CO'),'LIM':('Lima','PE'),
    'DUB':('Dublin','IE'),'KEF':('Reykjavik','IS'),'LUX':('Luxembourg','LU'),
    'MLA':('Malta','MT'),'LCA':('Larnaca','CY'),
    'OTP':('Bucharest','RO'),'SOF':('Sofia','BG'),'BEG':('Belgrade','RS'),
    'ZAG':('Zagreb','HR'),'DBV':('Dubrovnik','HR'),'SPU':('Split','HR'),
    'LJU':('Ljubljana','SI'),'SKP':('Skopje','MK'),'TIA':('Tirana','AL'),
    'RIX':('Riga','LV'),'TLL':('Tallinn','EE'),'VNO':('Vilnius','LT'),
    'SVO':('Moscow','RU'),'LED':('St Petersburg','RU'),
    'GYD':('Baku','AZ'),'TBS':('Tbilisi','GE'),'EVN':('Yerevan','AM'),
    'CUN':('Cancun','MX'),'MEX':('Mexico City','MX'),
    'MBJ':('Montego Bay','JM'),'PUJ':('Punta Cana','DO'),
    'AAC':('El Arish','EG'),
    'AAE':('Annaba','DZ'),
    'AAN':('Al Ain','AE'),
    'AAQ':('Krasnyi Kurg','RU'),
    'AAR':('Aarhus','DK'),
    'ABA':('Abakan','RU'),
    'ABB':('Asaba','NG'),
    'ABQ':('Albuquerque','US'),
    'ABV':('Abuja','NG'),
    'ABZ':('Aberdeen','GB'),
    'ACA':('Acapulco','MX'),
    'ACC':('Accra','GH'),
    'ACH':('St. Gallen','CH'),
    'ADA':('Seyhan','TR'),
    'ADF':('Adıyaman','TR'),
    'ADJ':('Amman','JO'),
    'ADL':('Adelaide','AU'),
    'ADZ':('San Andrés','CO'),
    'AEP':('Buenos Aires','AR'),
    'AER':('Sochi','RU'),
    'AES':('Ålesund','NO'),
    'AEY':('Akureyri','IS'),
    'AGA':('Al Massira','MA'),
    'AGH':('Ängelholm','SE'),
    'AGU':('Aguascalient','MX'),
    'AHB':('Abha','SA'),
    'AHO':('Alghero','IT'),
    'AJA':('Ajaccio','FR'),
    'AJF':('Al-Jawf','SA'),
    'AJI':('Ağrı','TR'),
    'AJR':('Arvidsjaur','SE'),
    'ALB':('Albany','US'),
    'ALF':('Alta','NO'),
    'ALG':('Algiers','DZ'),
    'AMD':('Ahmedabad','IN'),
    'AMQ':('Ambon','ID'),
    'AMV':('Amderma','RU'),
    'ANC':('Anchorage','US'),
    'ANF':('Antofagasta','CL'),
    'ANR':('Antwerp','BE'),
    'ANX':('Andenes','NO'),
    'AOE':('Eskişehir','TR'),
    'AOI':('Marche','IT'),
    'AOJ':('Aomori','JP'),
    'AOK':('Karpathos','GR'),
    'AQI':('Qaisumah','SA'),
    'AQJ':('Aqaba','JO'),
    'AQP':('Arequipa','PE'),
    'ARH':('Talagi','RU'),
    'ARW':('Arad','RO'),
    'ASF':('Astrakhan','RU'),
    'ASR':('Kayseri','TR'),
    'ASW':('Aswan','EG'),
    'ATQ':('Amritsar','IN'),
    'ATZ':('Asyut','EG'),
    'AUR':('Aurillac','FR'),
    'AUS':('Austin','US'),
    'AVN':('Avignon','FR'),
    'AVV':('Melbourne Av','AU'),
    'AWA':('Hawassa','ET'),
    'AXD':('Alexandroupo','GR'),
    'AZI':('Abu Dhabi','AE'),
    'BAH':('Manama','BH'),
    'BAL':('Batman','TR'),
    'BAQ':('Barranquilla','CO'),
    'BAV':('Baotou','CN'),
    'BAX':('Barnaul','RU'),
    'BAY':('Maramureș','RO'),
    'BBI':('Bhubaneswar','IN'),
    'BBU':('Bucharest','RO'),
    'BCD':('Bacolod City','PH'),
    'BCM':('Bacău','RO'),
    'BCU':('Bauchi','NG'),
    'BDJ':('Banjarbaru','ID'),
    'BDL':('Bradley','US'),
    'BDQ':('Vadodara','IN'),
    'BDS':('Brindisi','IT'),
    'BDU':('Målselv','NO'),
    'BEB':('Benbecula','GB'),
    'BEL':('Belém','BR'),
    'BEM':('Oulad Yaich','MA'),
    'BES':('Brest','FR'),
    'BFN':('Bloemfontein','ZA'),
    'BFS':('Belfast','GB'),
    'BGC':('Bragança','PT'),
    'BGO':('Bergen','NO'),
    'BHD':('Belfast','GB'),
    'BHM':('Birmingham','US'),
    'BHO':('Bhopal','IN'),
    'BIA':('Bastia','FR'),
    'BIO':('Bilbao','ES'),
    'BIQ':('Biarritz','FR'),
    'BJA':('Béjaïa','DZ'),
    'BJF':('Båtsfjord','NO'),
    'BJX':('Silao','MX'),
    'BJZ':('Badajoz','ES'),
    'BKI':('Kota Kinabal','MY'),
    'BLE':('Dala','SE'),
    'BLJ':('Batna','DZ'),
    'BLL':('Billund','DK'),
    'BMA':('Stockholm','SE'),
    'BME':('Broome','AU'),
    'BNA':('Nashville','US'),
    'BNN':('Brønnøy','NO'),
    'BNX':('Mahovljani','BA'),
    'BOH':('Bournemouth','GB'),
    'BOI':('Boise','US'),
    'BOJ':('Burgas','BG'),
    'BOO':('Bodø','NO'),
    'BPN':('Balikpapan','ID'),
    'BPS':('Porto Seguro','BR'),
    'BQS':('Ignatyevo','RU'),
    'BQT':('Brest','BY'),
    'BRC':('San Carlos d','AR'),
    'BRE':('Bremen','DE'),
    'BRI':('Bari','IT'),
    'BRN':('Bern','CH'),
    'BRQ':('Brno','CZ'),
    'BRR':('Barra','GB'),
    'BSB':('Brasília','BR'),
    'BSK':('Biskra','DZ'),
    'BTH':('Batam','ID'),
    'BTJ':('Banda Aceh','ID'),
    'BTK':('Bratsk','RU'),
    'BUF':('Buffalo','US'),
    'BUR':('Burbank','US'),
    'BUS':('Batumi','GE'),
    'BVA':('Beauvais','FR'),
    'BVB':('Boa Vista','BR'),
    'BVE':('Brive','FR'),
    'BVG':('Berlevåg','NO'),
    'BVJ':('Bovanenkovo','RU'),
    'BWI':('Baltimore','US'),
    'BWK':('Brač','HR'),
    'BWO':('Balakovo','RU'),
    'BZG':('Bydgoszcz','PL'),
    'BZI':('Balıkesir','TR'),
    'BZK':('Bryansk','RU'),
    'BZO':('Bolzano','IT'),
    'BZR':('Béziers','FR'),
    'CAG':('Cagliari','IT'),
    'CAL':('Campbeltown','GB'),
    'CAN':('Guangzhou Ba','CN'),
    'CAT':('Cascais','PT'),
    'CCF':('Carcassonne','FR'),
    'CCJ':('Calicut','IN'),
    'CCP':('Concepcion','CL'),
    'CCU':('Kolkata','IN'),
    'CDT':('Castellón de','ES'),
    'CEB':('Mactan Cebu','PH'),
    'CEE':('Cherepovets','RU'),
    'CEI':('Chiang Rai','TH'),
    'CEK':('Chelyabinsk','RU'),
    'CFE':('Clermont-Fer','FR'),
    'CFK':('Chlef','DZ'),
    'CFN':('Donegal','IE'),
    'CFR':('Caen','FR'),
    'CGB':('Cuiabá','BR'),
    'CGH':('São Paulo','BR'),
    'CGO':('Zhengzhou','CN'),
    'CGQ':('Changchun','CN'),
    'CGY':('Laguindingan','PH'),
    'CHC':('Christchurch','NZ'),
    'CHQ':('Souda','GR'),
    'CHS':('Charleston','US'),
    'CIA':('Rome','IT'),
    'CIX':('Chiclayo','PE'),
    'CIY':('Comiso','IT'),
    'CJB':('Coimbatore','IN'),
    'CJJ':('Cheongju','KR'),
    'CJS':('Ciudad Juáre','MX'),
    'CJU':('Jeju','KR'),
    'CKG':('Chongqing','CN'),
    'CKH':('Chokurdah','RU'),
    'CKZ':('Çanakkale','TR'),
    'CLE':('Cleveland','US'),
    'CLJ':('Cluj-Napoca','RO'),
    'CLO':('Cali','CO'),
    'CLT':('Charlotte','US'),
    'CLY':('Calvi','FR'),
    'CMF':('Chambéry','FR'),
    'CMH':('Columbus','US'),
    'CND':('Constanța','RO'),
    'CNF':('Belo Horizon','BR'),
    'CNN':('Kannur','IN'),
    'CNS':('Cairns','AU'),
    'CNX':('Chiang Mai','TH'),
    'COK':('Kochi','IN'),
    'COR':('Cordoba','AR'),
    'COS':('Colorado Spr','US'),
    'COV':('Tarsus','TR'),
    'CRA':('Craiova','RO'),
    'CRD':('Comodoro Riv','AR'),
    'CRK':('Mabalacat','PH'),
    'CRV':('Isola di Cap','IT'),
    'CSX':('Changsha Hua','CN'),
    'CSY':('Cheboksary','RU'),
    'CTG':('Cartagena','CO'),
    'CTS':('Sapporo','JP'),
    'CTU':('Chengdu Shua','CN'),
    'CUF':('Cuneo','IT'),
    'CUL':('Culiacán','MX'),
    'CUU':('Chihuahua','MX'),
    'CUZ':('Cusco','PE'),
    'CVG':('Cincinnati /','US'),
    'CWB':('Curitiba','BR'),
    'CWC':('Chernivtsi','UA'),
    'CWL':('Cardiff','GB'),
    'CXR':('Cam Ranh / C','VN'),
    'CYX':('Cherskiy','RU'),
    'CZL':('Constantine','DZ'),
    'CZM':('Cozumel','MX'),
    'DAD':('Da Nang','VN'),
    'DAT':('Datong','CN'),
    'DBB':('El Alamein','EG'),
    'DCA':('Washington','US'),
    'DCM':('Castres','FR'),
    'DEB':('Debrecen','HU'),
    'DHA':('Dhahran','SA'),
    'DIA':('Doha','QA'),
    'DIJ':('Dijon','FR'),
    'DIR':('Dire Dawa','ET'),
    'DIY':('Diyarbakır','TR'),
    'DJE':('Mellita','TN'),
    'DJG':('Djanet','DZ'),
    'DJJ':('Sentani','ID'),
    'DKR':('Dakar','SN'),
    'DLC':('Dalian Zhous','CN'),
    'DLE':('Dole','FR'),
    'DME':('Moscow','RU'),
    'DMK':('Bangkok','TH'),
    'DMM':('Ad Dammam','SA'),
    'DNA':('Okinawa','JP'),
    'DND':('Dundee','GB'),
    'DNH':('Dunhuang','CN'),
    'DNK':('Dnipro','UA'),
    'DNR':('Dinard','FR'),
    'DNZ':('Çardak','TR'),
    'DOL':('Deauville','FR'),
    'DQM':('Duqm','OM'),
    'DRP':('Bicol','PH'),
    'DRS':('Dresden','DE'),
    'DRW':('Darwin','AU'),
    'DSM':('Des Moines','US'),
    'DSN':('Ordos','CN'),
    'DSS':('Dakar','SN'),
    'DTM':('Dortmund','DE'),
    'DTW':('Detroit','US'),
    'DUR':('Durban','ZA'),
    'DVO':('Davao','PH'),
    'DWC':('Al Maktoum','AE'),
    'DXN':('Noida','IN'),
    'DYG':('Zhangjiajie ','CN'),
    'DYR':('Anadyr','RU'),
    'EAS':('Hondarribia','ES'),
    'EBA':('Marina di Ca','IT'),
    'EBJ':('Esbjerg','DK'),
    'ECN':('Ercan','CY'),
    'EDL':('Eldoret','KE'),
    'EDO':('Edremit','TR'),
    'EES':('Berenice Tro','EG'),
    'EFL':('Kefallinia','GR'),
    'EGC':('Bergerac','FR'),
    'EGO':('Belgorod','RU'),
    'EGS':('Egilsstaðir','IS'),
    'EHU':('Ezhou','CN'),
    'EIE':('Yeniseysk','RU'),
    'EIK':('Yeysk','RU'),
    'ELP':('El Paso','US'),
    'ELQ':('Qassim','SA'),
    'ELS':('King Phalo','ZA'),
    'EMA':('East Midland','GB'),
    'ENF':('Enontekio','FI'),
    'ENU':('Enegu','NG'),
    'EOI':('Eday','GB'),
    'EPU':('Pärnu','EE'),
    'ERC':('Erzincan','TR'),
    'ERF':('Erfurt','DE'),
    'ERZ':('Erzurum','TR'),
    'ESB':('Ankara','TR'),
    'ESL':('Elista','RU'),
    'ETM':('Eilat','IL'),
    'ETZ':('Goin','FR'),
    'EVE':('Evenes','NO'),
    'EXT':('Exeter','GB'),
    'EYK':('Beloyarskiy','RU'),
    'EZS':('Elazığ','TR'),
    'FAT':('Fresno','US'),
    'FCN':('Wurster Nord','DE'),
    'FDH':('Friedrichsha','DE'),
    'FEZ':('Saïss','MA'),
    'FJR':('Fujairah','AE'),
    'FKB':('Rheinmünster','DE'),
    'FLL':('Fort Lauderd','US'),
    'FLN':('Hercílio Luz','BR'),
    'FLW':('Flores','PT'),
    'FMM':('Memmingen','DE'),
    'FMO':('Greven','DE'),
    'FNI':('Nîmes/Garons','FR'),
    'FOC':('Fuzhou Chang','CN'),
    'FOG':('Foggia (FG)','IT'),
    'FOR':('Fortaleza','BR'),
    'FRL':('Forlì (FC)','IT'),
    'FRO':('Florø','NO'),
    'FSC':('Figari','FR'),
    'FSZ':('Mount Fuji S','JP'),
    'FTE':('El Calafate','AR'),
    'FUK':('Fukuoka','JP'),
    'GAU':('Guwahati','IN'),
    'GBB':('Gabala','AZ'),
    'GDL':('Guadalajara','MX'),
    'GDX':('Sokol','RU'),
    'GDZ':('Gelendzhik','RU'),
    'GEC':('Lefkoniko (G','CY'),
    'GEG':('Spokane','US'),
    'GES':('General Sant','PH'),
    'GEV':('Gällivare','SE'),
    'GHV':('Brașov-Ghimb','RO'),
    'GIG':('Rio De Janei','BR'),
    'GJL':('Tahir','DZ'),
    'GME':('Gomel','BY'),
    'GMP':('Seoul','KR'),
    'GNB':('Grenoble','FR'),
    'GNJ':('Ganja','AZ'),
    'GNY':('Şanlıurfa','TR'),
    'GOA':('Genova (GE)','IT'),
    'GOI':('Goa Dabolim','IN'),
    'GOJ':('Nizhny Novgo','RU'),
    'GOX':('Mopa','IN'),
    'GPA':('Patras','GR'),
    'GRJ':('George','ZA'),
    'GRO':('Girona','ES'),
    'GRQ':('Groningen','NL'),
    'GRR':('Grand Rapids','US'),
    'GRV':('Grozny','RU'),
    'GRW':('Graciosa','PT'),
    'GRX':('Granada','ES'),
    'GRY':('Grímsey','IS'),
    'GSO':('Greensboro','US'),
    'GSV':('Saratov','RU'),
    'GWT':('Sylt','DE'),
    'GYN':('Goiânia','BR'),
    'GZP':('Gazipaşa','TR'),
    'GZT':('Gaziantep','TR'),
    'HAD':('Halmstad','SE'),
    'HAJ':('Hannover','DE'),
    'HAK':('Haikou Meila','CN'),
    'HAN':('Noi Bai','VN'),
    'HAS':('Hail','SA'),
    'HAU':('Karmøy','NO'),
    'HBA':('Hobart','AU'),
    'HBE':('Alexandria','EG'),
    'HDF':('Zirchow','DE'),
    'HDY':('Hat Yai','TH'),
    'HET':('Hohhot','CN'),
    'HFE':('Hefei','CN'),
    'HFN':('Höfn','IS'),
    'HFT':('Hammerfest','NO'),
    'HGH':('Hangzhou','CN'),
    'HHN':('Frankfurt-Ha','DE'),
    'HIA':('Huaian','CN'),
    'HIJ':('Hiroshima','JP'),
    'HKD':('Hakodate','JP'),
    'HLA':('Lanseria','ZA'),
    'HLD':('Hailar','CN'),
    'HLP':('Jakarta','ID'),
    'HMA':('Khanty-Mansi','RU'),
    'HMB':('Suhaj','EG'),
    'HMO':('Hermosillo','MX'),
    'HNL':('Honolulu, Oa','US'),
    'HOF':('Hofuf','SA'),
    'HOR':('Horta','PT'),
    'HOU':('Houston','US'),
    'HOV':('Ørsta','NO'),
    'HPH':('Cat Bi','VN'),
    'HRB':('Harbin','CN'),
    'HRG':('Hurghada','EG'),
    'HSG':('Saga','JP'),
    'HSN':('Zhoushan','CN'),
    'HSR':('Rajkot','IN'),
    'HSS':('Hisar','IN'),
    'HTA':('Chita','RU'),
    'HTG':('Khatanga','RU'),
    'HTY':('Hatay','TR'),
    'HUX':('Huatulco','MX'),
    'HUY':('Humberside','GB'),
    'HVG':('Honningsvåg','NO'),
    'HWR':('Halwara','IN'),
    'HYD':('Hyderabad','IN'),
    'IAA':('Igarka','RU'),
    'IAH':('Houston','US'),
    'IAR':('Tunoshna','RU'),
    'IAS':('Iaşi','RO'),
    'IBR':('Omitama','JP'),
    'IDR':('Indore','IN'),
    'IEG':('Nowe Kramsko','PL'),
    'IEV':('Kyiv','UA'),
    'IFJ':('Ísafjörður','IS'),
    'IFO':('Ivano-Franki','UA'),
    'IGD':('Iğdır','TR'),
    'IGT':('Magas','RU'),
    'IGU':('Cataratas','BR'),
    'IJK':('Izhevsk','RU'),
    'IKS':('Tiksi','RU'),
    'IKT':('Irkutsk','RU'),
    'ILD':('Lleida','ES'),
    'ILO':('Iloilo','PH'),
    'ILR':('Ilorin/Ogbom','NG'),
    'ILY':('Islay','GB'),
    'IMF':('Imphal','IN'),
    'INC':('Yinchuan','CN'),
    'IND':('Indianapolis','US'),
    'INI':('Niš','RS'),
    'INV':('Inverness','GB'),
    'IOA':('Ioannina','GR'),
    'IPC':('Mataveri','CL'),
    'IPH':('Ipoh','MY'),
    'IQQ':('Iquique','CL'),
    'IQT':('Iquitos','PE'),
    'ISE':('Isparta','TR'),
    'ISK':('Nashik','IN'),
    'ISL':('İstanbul Ata','TR'),
    'ITM':('Osaka','JP'),
    'IVL':('Ivalo','FI'),
    'IWA':('Ivanovo','RU'),
    'IXB':('Siliguri','IN'),
    'IXC':('Chandigarh','IN'),
    'IXE':('Mangaluru','IN'),
    'IXZ':('Port Blair','IN'),
    'JAI':('Jaipur','IN'),
    'JAX':('Jacksonville','US'),
    'JCL':('České Budějo','CZ'),
    'JGN':('Jiayuguan','CN'),
    'JHB':('Senai','MY'),
    'JHG':('Jinghong (Ga','CN'),
    'JIJ':('Jijiga','ET'),
    'JJN':('Quanzhou','CN'),
    'JKG':('Jönköping','SE'),
    'JKH':('Chios Island','GR'),
    'JMK':('Mykonos','GR'),
    'JOE':('Joensuu','FI'),
    'JPA':('João Pessoa','BR'),
    'JSH':('Sitia','GR'),
    'JSI':('Skiathos','GR'),
    'JUJ':('San Salvador','AR'),
    'JUL':('Juliaca','PE'),
    'JYV':('Jyväskylä','FI'),
    'KAD':('Kaduna','NG'),
    'KAJ':('Kajaani','FI'),
    'KAN':('Kano','NG'),
    'KAO':('Kuusamo','FI'),
    'KBV':('Krabi','TH'),
    'KCH':('Kuching','MY'),
    'KCM':('Kahramanmara','TR'),
    'KCY':('Krasnoyarsk','RU'),
    'KCZ':('Nankoku','JP'),
    'KDL':('Kärdla','EE'),
    'KEJ':('Kemerovo','RU'),
    'KEM':('Kemi-Tornio','FI'),
    'KGD':('Khrabrovo','RU'),
    'KGP':('Kogalym','RU'),
    'KGS':('Kos Island','GR'),
    'KHE':('Kherson','UA'),
    'KHG':('Kashgar','CN'),
    'KHN':('Nanchang','CN'),
    'KHV':('Khabarovsk','RU'),
    'KIJ':('Niigata','JP'),
    'KIM':('Kimberley','ZA'),
    'KIN':('Kingston','JM'),
    'KIR':('Kerry','IE'),
    'KIS':('Kisumu','KE'),
    'KJA':('Krasnoyarsk','RU'),
    'KKJ':('Kitakyushu','JP'),
    'KKN':('Kirkenes','NO'),
    'KLO':('Kalibo','PH'),
    'KLR':('Kalmar','SE'),
    'KLU':('Klagenfurt','AT'),
    'KLV':('Karlovy Vary','CZ'),
    'KLX':('Kalamata','GR'),
    'KMG':('Kunming','CN'),
    'KMI':('Miyazaki','JP'),
    'KMJ':('Kumamoto','JP'),
    'KMQ':('Kanazawa','JP'),
    'KMS':('Kumasi','GH'),
    'KMW':('Kostroma','RU'),
    'KNO':('Beringin','ID'),
    'KOA':('Kailua-Kona','US'),
    'KOI':('Kirkwall','GB'),
    'KOJ':('Kagoshima','JP'),
    'KOK':('Kokkola / Kr','FI'),
    'KPW':('Keperveem','RU'),
    'KRF':('Nyland','SE'),
    'KRN':('Kiruna','SE'),
    'KRO':('Kurgan','RU'),
    'KRP':('Karup','DK'),
    'KRR':('Krasnodar','RU'),
    'KRS':('Kristiansand','NO'),
    'KSC':('Košice','SK'),
    'KSD':('Karlstad','SE'),
    'KSF':('Calden','DE'),
    'KSU':('Kvernberget','NO'),
    'KSY':('Kars','TR'),
    'KSZ':('Kotlas','RU'),
    'KTT':('Kittilä','FI'),
    'KTW':('Katowice','PL'),
    'KUF':('Samara','RU'),
    'KUN':('Kaunas','LT'),
    'KUO':('Kuopio','FI'),
    'KUT':('Kopitnari','GE'),
    'KVA':('Kavala','GR'),
    'KVO':('Morava','RS'),
    'KVX':('Kirov','RU'),
    'KWE':('Guiyang (Nan','CN'),
    'KWG':('Kryvyi Rih','UA'),
    'KWI':('Kuwait','KW'),
    'KWL':('Guilin (Ling','CN'),
    'KXK':('Komsomolsk-o','RU'),
    'KYA':('Konya','TR'),
    'KYZ':('Kyzyl','RU'),
    'KZI':('Kozani','GR'),
    'KZN':('Kazan','RU'),
    'LAO':('Laoag','PH'),
    'LBA':('Leeds Bradfo','GB'),
    'LBC':('Lübeck','DE'),
    'LCG':('A Coruña','ES'),
    'LCJ':('Łódź','PL'),
    'LDE':('Tarbes/Lourd','FR'),
    'LDY':('City of Derr','GB'),
    'LEI':('Almería','ES'),
    'LEJ':('Schkeuditz','DE'),
    'LEN':('León','ES'),
    'LEU':('Pirineus - l','ES'),
    'LGA':('New York','US'),
    'LGB':('Long Beach','US'),
    'LGG':('Liège','BE'),
    'LGK':('Langkawi','MY'),
    'LHL':('Lachin','AZ'),
    'LHW':('Lanzhou (Yon','CN'),
    'LIG':('Limoges','FR'),
    'LIH':('Lihue','US'),
    'LIL':('Lille','FR'),
    'LJG':('Lijiang','CN'),
    'LKL':('Lakselv','NO'),
    'LKN':('Leknes','NO'),
    'LKO':('Lucknow','IN'),
    'LLA':('Luleå','SE'),
    'LME':('Le Mans-Arna','FR'),
    'LMP':('Lampedusa','IT'),
    'LNZ':('Linz','AT'),
    'LOP':('Lombok','ID'),
    'LOS':('Lagos','NG'),
    'LPI':('Linköping','SE'),
    'LPK':('Lipetsk','RU'),
    'LPL':('Liverpool','GB'),
    'LPP':('Lappeenranta','FI'),
    'LPX':('Liepāja','LV'),
    'LRH':('La Rochelle','FR'),
    'LRM':('La Romana','DO'),
    'LRT':('Lorient/Lann','FR'),
    'LSI':('Sumburgh','GB'),
    'LTH':('Ho Chi Minh ','VN'),
    'LTO':('Loreto','MX'),
    'LUG':('Agno','CH'),
    'LUZ':('Lublin','PL'),
    'LWN':('Gyumri','AM'),
    'LWO':('Lviv','UA'),
    'LXA':('Lhasa Gongga','CN'),
    'LXR':('Luxor','EG'),
    'LYA':('Luoyang Beij','CN'),
    'LYC':('Lycksele','SE'),
    'LYG':('Lianyungang','CN'),
    'LYR':('Longyearbyen','NO'),
    'MAA':('Chennai','IN'),
    'MAH':('Menorca','ES'),
    'MAO':('Manaus','BR'),
    'MBA':('Moi','KE'),
    'MBX':('Maribor','SI'),
    'MCI':('Kansas City','US'),
    'MCT':('Muscat','OM'),
    'MCX':('Makhachkala','RU'),
    'MCY':('Maroochydore','AU'),
    'MCZ':('Maceió','BR'),
    'MDC':('Manado','ID'),
    'MDE':('Medellín','CO'),
    'MDW':('Chicago','US'),
    'MDZ':('Mendoza','AR'),
    'MED':('Medina','SA'),
    'MEH':('Mehamn','NO'),
    'MEM':('Memphis','US'),
    'MHG':('Mannheim','DE'),
    'MHQ':('Mariehamn','FI'),
    'MID':('Mérida','MX'),
    'MIU':('Maiduguri','NG'),
    'MJF':('Mosjøen','NO'),
    'MJT':('Mytilene','GR'),
    'MJZ':('Mirny','RU'),
    'MKE':('Milwaukee','US'),
    'MLM':('Morelia','MX'),
    'MLN':('Melilla','ES'),
    'MLX':('Malatya','TR'),
    'MME':('Teesside','GB'),
    'MMK':('Murmansk','RU'),
    'MMX':('Malmö','SE'),
    'MNL':('Ninoy Aquino','PH'),
    'MOL':('Årø','NO'),
    'MPL':('Montpellier/','FR'),
    'MPW':('Mariupol','UA'),
    'MQF':('Magnitogorsk','RU'),
    'MQJ':('Moma','RU'),
    'MQM':('Mardin','TR'),
    'MQN':('Mo i Rana','NO'),
    'MQP':('Mbombela','ZA'),
    'MRU':('Plaine Magni','MU'),
    'MRV':('Mineralnye V','RU'),
    'MSP':('Minneapolis','US'),
    'MSQ':('Minsk','BY'),
    'MSR':('Muş','TR'),
    'MST':('Maastricht','NL'),
    'MSY':('New Orleans','US'),
    'MTY':('Monterrey','MX'),
    'MUH':('Marsa Matruh','EG'),
    'MVQ':('Mogilev','BY'),
    'MWX':('Muan','KR'),
    'MXX':('Mora','SE'),
    'MYJ':('Matsuyama','JP'),
    'MYR':('Myrtle Beach','US'),
    'MZT':('Mazatlàn','MX'),
    'NAG':('Nagpur','IN'),
    'NAJ':('Nakhchivan','AZ'),
    'NAL':('Nalchik','RU'),
    'NAT':('Natal','BR'),
    'NAV':('Nevşehir','TR'),
    'NBC':('Begishevo','RU'),
    'NCY':('Annecy','FR'),
    'NDG':('Qiqihar','CN'),
    'NDR':('Al Aaroui','MA'),
    'NER':('Chulman','RU'),
    'NFG':('Nefteyugansk','RU'),
    'NGB':('Ningbo','CN'),
    'NGO':('Tokoname','JP'),
    'NGS':('Nagasaki','JP'),
    'NJC':('Nizhnevartov','RU'),
    'NKG':('Nanjing','CN'),
    'NKT':('Şırnak','TR'),
    'NLI':('Nikolayevsk-','RU'),
    'NLU':('Mexico City','MX'),
    'NMI':('Navi Mumbai','IN'),
    'NNG':('Nanning Wuxu','CN'),
    'NNM':('Naryan Mar','RU'),
    'NOC':('Charlestown','IE'),
    'NOJ':('Noyabrsk','RU'),
    'NOP':('Sinop','TR'),
    'NOZ':('Spichenkovo','RU'),
    'NQN':('Neuquén','AR'),
    'NQY':('Newquay','GB'),
    'NRK':('Norrköping','SE'),
    'NRN':('Weeze','DE'),
    'NSK':('Alykel','RU'),
    'NTL':('Newcastle','AU'),
    'NUM':('Sharma','SA'),
    'NUX':('Novy Urengoy','RU'),
    'NVT':('Navegantes','BR'),
    'NWI':('Norwich','GB'),
    'NYA':('Nyagan','RU'),
    'NYM':('Nadym','RU'),
    'NYO':('Nyköping','SE'),
    'OAK':('Oakland','US'),
    'OAX':('Oaxaca','MX'),
    'ODE':('Odense','DK'),
    'ODS':('Odesa','UA'),
    'OER':('Örnsköldsvik','SE'),
    'OGG':('Kahului','US'),
    'OGU':('Ordu','TR'),
    'OGZ':('Beslan','RU'),
    'OHD':('Ohrid','MK'),
    'OHO':('Okhotsk','RU'),
    'OHS':('Suhar','OM'),
    'OKA':('Naha','JP'),
    'OKC':('Oklahoma Cit','US'),
    'OKJ':('Okayama','JP'),
    'OLA':('Ørland','NO'),
    'OLB':('Olbia (SS)','IT'),
    'OLZ':('Olyokminsk','RU'),
    'OMA':('Omaha','US'),
    'OMO':('Mostar','BA'),
    'OMR':('Oradea','RO'),
    'OMS':('Omsk','RU'),
    'ONQ':('Zonguldak','TR'),
    'ONT':('Ontario','US'),
    'OOL':('Gold Coast','AU'),
    'ORB':('Örebro','SE'),
    'ORF':('Norfolk','US'),
    'ORK':('Cork','IE'),
    'ORN':('Es-Sénia','DZ'),
    'OSD':('Östersund','SE'),
    'OSI':('Osijek','HR'),
    'OSR':('Mošnov','CZ'),
    'OST':('Oostende','BE'),
    'OSW':('Orsk','RU'),
    'OUD':('Ahl Angad','MA'),
    'OUL':('Oulu','FI'),
    'OVB':('Novosibirsk','RU'),
    'OVD':('Ranón','ES'),
    'OVS':('Sovetskiy','RU'),
    'OZG':('Zagora','MA'),
    'OZH':('Zaporizhia','UA'),
    'OZZ':('Ouarzazate','MA'),
    'PAD':('Büren','DE'),
    'PBC':('Puebla','MX'),
    'PBI':('Palm Beach','US'),
    'PCL':('Pucallpa','PE'),
    'PDG':('Minangkabau','ID'),
    'PDL':('Ponta Delgad','PT'),
    'PDV':('Plovdiv','BG'),
    'PDX':('Portland','US'),
    'PED':('Pardubice','CZ'),
    'PEE':('Perm','RU'),
    'PEG':('Perugia (PG)','IT'),
    'PEN':('Penang','MY'),
    'PER':('Perth','AU'),
    'PES':('Petrozavodsk','RU'),
    'PEV':('Pécs','HU'),
    'PEX':('Pechora','RU'),
    'PEZ':('Penza','RU'),
    'PFO':('Paphos','CY'),
    'PGF':('Perpignan/Ri','FR'),
    'PHC':('Port Harcour','NG'),
    'PHE':('Port Hedland','AU'),
    'PHL':('Philadelphia','US'),
    'PHX':('Phoenix','US'),
    'PIE':('Pinellas Par','US'),
    'PIK':('Glasgow Pres','GB'),
    'PIO':('Pisco','PE'),
    'PIS':('Poitiers/Bia','FR'),
    'PIT':('Pittsburgh','US'),
    'PIX':('Pico','PT'),
    'PKC':('Yelizovo','RU'),
    'PKV':('Pskov','RU'),
    'PKX':('Beijing','CN'),
    'PLQ':('Palanga','LT'),
    'PLZ':('Chief Dawid ','ZA'),
    'PMC':('El Tepual','CL'),
    'PMF':('Parma','IT'),
    'PNA':('Pamplona','ES'),
    'PNK':('Supadio','ID'),
    'PNL':('Pantelleria','IT'),
    'PNQ':('Pune','IN'),
    'PNS':('Pensacola','US'),
    'POA':('Porto Alegre','BR'),
    'POR':('Pori','FI'),
    'POZ':('Poznań','PL'),
    'PPS':('Puerto Princ','PH'),
    'PQC':('Phú Quốc','VN'),
    'PRM':('Portimão','PT'),
    'PSD':('Port Said','EG'),
    'PSP':('Palm Springs','US'),
    'PSR':('Pescara','IT'),
    'PTG':('Polokwane','ZA'),
    'PUF':('Pau Pyrénées','FR'),
    'PUQ':('Punta Arenas','CL'),
    'PUS':('Busan','KR'),
    'PUY':('Pula','HR'),
    'PVD':('Providence/W','US'),
    'PVH':('Porto Velho','BR'),
    'PVK':('Preveza','GR'),
    'PVR':('Puerto Valla','MX'),
    'PWE':('Pevek','RU'),
    'PWM':('Portland','US'),
    'PXO':('Porto Santo','PT'),
    'PYJ':('Yakutia','RU'),
    'QRO':('Querétaro','MX'),
    'QSR':('Salerno','IT'),
    'RBA':('Rabat','MA'),
    'RBR':('Rio Branco','BR'),
    'RDO':('Radom','PL'),
    'RDU':('Raleigh/Durh','US'),
    'RDZ':('Rodez–Aveyro','FR'),
    'REC':('Recife','BR'),
    'REG':('Reggio Calab','IT'),
    'REN':('Orenburg','RU'),
    'RES':('Resistencia','AR'),
    'REU':('Reus','ES'),
    'RGL':('Rio Gallegos','AR'),
    'RIC':('Richmond','US'),
    'RJK':('Rijeka','HR'),
    'RKE':('Roskilde','DK'),
    'RKT':('Ras Al Khaim','AE'),
    'RKV':('Reykjavík','IS'),
    'RKZ':('Xigazê (Samz','CN'),
    'RLG':('Laage','DE'),
    'RMF':('Marsa Alam','EG'),
    'RMI':('Rimini (RN)','IT'),
    'RMU':('Corvera','ES'),
    'RMZ':('Tobolsk','RU'),
    'RNB':('Ronneby','SE'),
    'RNN':('Rønne','DK'),
    'RNO':('Reno','US'),
    'RNS':('Rennes-Saint','FR'),
    'ROC':('Rochester','US'),
    'ROS':('Rosario','AR'),
    'ROV':('Platov','RU'),
    'RRS':('Røros','NO'),
    'RSI':('Hanak','SA'),
    'RSW':('Fort Myers','US'),
    'RTM':('Rotterdam','NL'),
    'RUN':('Sainte-Marie','RE'),
    'RVK':('Rørvik','NO'),
    'RVN':('Rovaniemi','FI'),
    'RWN':('Rivne','UA'),
    'RYB':('Rybinsk','RU'),
    'RZE':('Jasionka','PL'),
    'RZV':('Rize','TR'),
    'SAG':('Kakadi','IN'),
    'SAN':('San Diego','US'),
    'SAT':('San Antonio','US'),
    'SAV':('Savannah','US'),
    'SBD':('San Bernardi','US'),
    'SBT':('Sabetta','RU'),
    'SBZ':('Sibiu','RO'),
    'SCN':('Saarbrücken','DE'),
    'SCQ':('Santiago de ','ES'),
    'SCR':('Malung-Sälen','SE'),
    'SCV':('Suceava','RO'),
    'SCW':('Syktyvkar','RU'),
    'SDF':('Louisville','US'),
    'SDJ':('Natori','JP'),
    'SDL':('Sundsvall-Hä','SE'),
    'SDQ':('Las Américas','DO'),
    'SDR':('Santander','ES'),
    'SDU':('Santos Dumon','BR'),
    'SEK':('Srednekolyms','RU'),
    'SEN':('London South','GB'),
    'SFB':('Orlando','US'),
    'SFS':('Olongapo','PH'),
    'SFT':('Skellefteå','SE'),
    'SGC':('Surgut','RU'),
    'SGD':('Sønderborg','DK'),
    'SGN':('Tan Son Nhat','VN'),
    'SHA':('Shanghai Hon','CN'),
    'SHE':('Shenyang','CN'),
    'SHJ':('Sharjah','AE'),
    'SIP':('Simferopol','UA'),
    'SJC':('San Jose','US'),
    'SJD':('Los Cabos','MX'),
    'SJJ':('Sarajevo','BA'),
    'SJW':('Shijiazhuang','CN'),
    'SJZ':('Velas','PT'),
    'SKN':('Hadsel','NO'),
    'SKO':('Sokoto','NG'),
    'SKX':('Saransk','RU'),
    'SLA':('Salta','AR'),
    'SLC':('Salt Lake Ci','US'),
    'SLD':('Sliač','SK'),
    'SLL':('Salalah','OM'),
    'SLM':('Salamanca','ES'),
    'SLY':('Salekhard','RU'),
    'SLZ':('São Luís','BR'),
    'SMA':('Santa Maria','PT'),
    'SMF':('Sacramento','US'),
    'SMI':('Samos','GR'),
    'SNA':('Santa Ana','US'),
    'SNN':('Shannon','IE'),
    'SNR':('Saint-Nazair','FR'),
    'SOB':('Sármellék','HU'),
    'SOC':('Surakarta','ID'),
    'SOJ':('Sørkjosen','NO'),
    'SOU':('Southampton','GB'),
    'SPC':('La Palma','ES'),
    'SPX':('Sphinx','EG'),
    'SRG':('Semarang','ID'),
    'SRP':('Leirvik','NO'),
    'SRQ':('Sarasota/Bra','US'),
    'SSA':('Salvador','BR'),
    'SSH':('Sharm El She','EG'),
    'SSJ':('Alstahaug','NO'),
    'STI':('Cibao','DO'),
    'STL':('St Louis','US'),
    'STV':('Surat','IN'),
    'STW':('Stavropol','RU'),
    'SUB':('Juanda','ID'),
    'SUF':('Lamezia Term','IT'),
    'SUI':('Sukhumi','GE'),
    'SUJ':('Satu Mare','RO'),
    'SVG':('Stavanger','NO'),
    'SVJ':('Svolvær','NO'),
    'SVL':('Savonlinna','FI'),
    'SVQ':('Seville','ES'),
    'SVX':('Koltsovo','RU'),
    'SWA':('Jieyang Chao','CN'),
    'SXB':('Strasbourg','FR'),
    'SXR':('Srinagar','IN'),
    'SYR':('Syracuse','US'),
    'SYS':('Saskylakh','RU'),
    'SYX':('Sanya Phoeni','CN'),
    'SYY':('Stornoway','GB'),
    'SZB':('Subang','MY'),
    'SZF':('Samsun','TR'),
    'SZX':('Shenzhen','CN'),
    'SZY':('Szymany','PL'),
    'SZZ':('Szczecin(Gle','PL'),
    'TAE':('Daegu','KR'),
    'TAK':('Takamatsu','JP'),
    'TAO':('Qingdao Jiao','CN'),
    'TAT':('Poprad','SK'),
    'TAY':('Tartu','EE'),
    'TEQ':('Çorlu','TR'),
    'TER':('Lajes','PT'),
    'TFN':('Tenerife','ES'),
    'TFU':('Chengdu Tian','CN'),
    'TGD':('Podgorica','ME'),
    'TGK':('Taganrog','RU'),
    'TGM':('Recea','RO'),
    'THN':('Trollhättan','SE'),
    'TIF':('Taif','SA'),
    'TIJ':('Tijuana','MX'),
    'TIR':('Tirupati','IN'),
    'TIV':('Tivat','ME'),
    'TJK':('Tokat','TR'),
    'TJM':('Tyumen','RU'),
    'TKS':('Tokushima','JP'),
    'TKU':('Turku','FI'),
    'TLC':('Toluca','MX'),
    'TLM':('Zenata','DZ'),
    'TLN':('Hyères, Var','FR'),
    'TML':('Tamale','GH'),
    'TMP':('Tampere-Pirk','FI'),
    'TMR':('Tamanrasset','DZ'),
    'TNA':('Jinan Yaoqia','CN'),
    'TNG':('Tangier','MA'),
    'TOF':('Tomsk','RU'),
    'TOS':('Tromsø','NO'),
    'TPA':('Tampa','US'),
    'TPS':('Trapani (TP)','IT'),
    'TQO':('Tulum','MX'),
    'TRD':('Trondheim','NO'),
    'TRE':('Tiree','GB'),
    'TRF':('Sandefjord(T','NO'),
    'TRN':('Turin','IT'),
    'TRS':('Trieste','IT'),
    'TRU':('Trujillo','PE'),
    'TRV':('Thiruvananth','IN'),
    'TRZ':('Tiruchirappa','IN'),
    'TSF':('Treviso','IT'),
    'TSN':('Tianjin','CN'),
    'TSR':('Timişoara','RO'),
    'TTU':('Tétouan','MA'),
    'TUC':('San Miguel d','AR'),
    'TUF':('Tours Val de','FR'),
    'TUL':('Tulsa','US'),
    'TUN':('Tunis','TN'),
    'TUS':('Tucson','US'),
    'TUU':('Tabuk','SA'),
    'TXN':('Huangshan','CN'),
    'TYF':('Torsby','SE'),
    'TYN':('Taiyuan','CN'),
    'TYS':('McGhee Tyson','US'),
    'TZL':('Tuzla','BA'),
    'TZX':('Trabzon','TR'),
    'UCT':('Ukhta','RU'),
    'UDJ':('Uzhhorod','UA'),
    'UFA':('Ufa','RU'),
    'UKB':('Kobe','JP'),
    'UKX':('Ust-Kut','RU'),
    'ULH':('Al-Ula','SA'),
    'ULK':('Lensk','RU'),
    'ULV':('Ulyanovsk','RU'),
    'ULY':('Cherdakly','RU'),
    'UME':('Umeå','SE'),
    'UPG':('Makassar','ID'),
    'URC':('Ürümqi','CN'),
    'URE':('Kuressaare','EE'),
    'URJ':('Uray','RU'),
    'URS':('Kursk','RU'),
    'USK':('Usinsk','RU'),
    'USM':('Samui','TH'),
    'USR':('Ust-Nera','RU'),
    'UTH':('Udon Thani','TH'),
    'UTP':('Rayong','TH'),
    'UUA':('Bugulma','RU'),
    'UUD':('Baikal','RU'),
    'UUS':('Yuzhno-Sakha','RU'),
    'VAA':('Vaasa','FI'),
    'VAN':('Van','TR'),
    'VAQ':('Vanavara','RU'),
    'VAR':('Varna','BG'),
    'VAW':('Vardø','NO'),
    'VBS':('Montichiari ','IT'),
    'VBY':('Visby','SE'),
    'VCA':('Can Tho','VN'),
    'VCP':('Campinas','BR'),
    'VDE':('El Hierro','ES'),
    'VDS':('Vadsø','NO'),
    'VEO':('Severo-Yenis','RU'),
    'VER':('Veracruz','MX'),
    'VGA':('Vijayawada','IN'),
    'VGO':('Vigo','ES'),
    'VHM':('Vilhelmina','SE'),
    'VIT':('Alava','ES'),
    'VIX':('Vitória','BR'),
    'VKO':('Moscow','RU'),
    'VKT':('Vorkuta','RU'),
    'VLL':('Valladolid','ES'),
    'VNS':('Varanasi','IN'),
    'VOG':('Volgograd','RU'),
    'VOL':('Nea Anchialo','GR'),
    'VOZ':('Voronezh','RU'),
    'VPN':('Vopnafjörður','IS'),
    'VRL':('Vila Real','PT'),
    'VSA':('Villahermosa','MX'),
    'VSE':('Viseu','PT'),
    'VST':('Stockholm Vä','SE'),
    'VTZ':('Visakhapatna','IN'),
    'VUS':('Velikiy Usty','RU'),
    'VVO':('Artyom','RU'),
    'VXO':('Växjö','SE'),
    'VYI':('Vilyuisk','RU'),
    'WIC':('Wick','GB'),
    'WLG':('Wellington','NZ'),
    'WMI':('Warsaw Modli','PL'),
    'WNZ':('Wenzhou Long','CN'),
    'WRO':('Wrocław','PL'),
    'WSI':('Sydney','AU'),
    'WTB':('Toowoomba','AU'),
    'WUH':('Wuhan Tianhe','CN'),
    'WUX':('Wuxi','CN'),
    'XCR':('Chalons en C','FR'),
    'XIY':('Xian','CN'),
    'XMN':('Xiamen','CN'),
    'XNN':('Xining Caoji','CN'),
    'XRY':('Jerez','ES'),
    'YCU':('Yuncheng Yan','CN'),
    'YEG':('Edmonton','CA'),
    'YEI':('Yenişehir','TR'),
    'YHZ':('Halifax','CA'),
    'YIA':('Yogyakarta','ID'),
    'YIW':('Yiwu','CN'),
    'YKO':('Hakkari','TR'),
    'YKS':('Yakutsk','RU'),
    'YLW':('Kelowna','CA'),
    'YNB':('Yanbu','SA'),
    'YNT':('Yantai','CN'),
    'YNY':('Yangyang','KR'),
    'YNZ':('Yancheng Nan','CN'),
    'YOW':('Ottawa','CA'),
    'YQB':('Quebec','CA'),
    'YWG':('Winnipeg','CA'),
    'YXE':('Saskatoon','CA'),
    'YYC':('Calgary','CA'),
    'YYJ':('Victoria','CA'),
    'YYT':('St. Johns','CA'),
    'ZAD':('Zadar','HR'),
    'ZAM':('Zamboanga','PH'),
    'ZAZ':('Zaragoza','ES'),
    'ZCO':('Temuco','CL'),
    'ZHA':('Zhanjiang','CN'),
    'ZIA':('Moscow','RU'),
    'ZIH':('Ixtapa','MX'),
    'ZIX':('Zhigansk','RU'),
    'ZKP':('Zyryanka','RU'),
    'ZQN':('Queenstown','NZ'),
    'ZSE':('Saint-Pierre','RE'),
    'ZTH':('Zakynthos','GR'),
    'ZUH':('Zhuhai Jinwa','CN'),
}

AIRCRAFT_NAMES = {
    'A318':'Airbus A318','A319':'Airbus A319','A320':'Airbus A320',
    'A321':'Airbus A321','A20N':'Airbus A320neo','A21N':'Airbus A321neo',
    'A332':'Airbus A330','A333':'Airbus A330','A359':'Airbus A350-900',
    'A35K':'Airbus A350-1000','A388':'Airbus A380',
    'B737':'Boeing 737','B738':'Boeing 737-800','B38M':'Boeing 737 MAX',
    'B744':'Boeing 747-400','B748':'Boeing 747-8',
    'B77W':'Boeing 777-300ER','B772':'Boeing 777-200',
    'B788':'Boeing 787-8','B789':'Boeing 787-9','B78X':'Boeing 787-10',
    'E170':'Embraer 170','E175':'Embraer 175',
    'E190':'Embraer 190','E195':'Embraer 195',
    'BCS1':'Airbus A220-100','BCS3':'Airbus A220-300',
    'C172':'Cessna 172','C182':'Cessna 182','C208':'Cessna Caravan',
    'PC12':'Pilatus PC-12','E55P':'Embraer Phenom',
    'C525':'Citation CJ','C56X':'Citation XLS',
    'GL5T':'Gulfstream G500','GLEX':'Global Express',
    'DH8D':'Dash 8 Q400','AT76':'ATR 72-600',
}

def lookup_airline_hex(hex_code, requests_session):
    """Look up airline/operator from ICAO hex code via hexdb.io"""
    try:
        url = HEXDB_URL + hex_code.upper()
        resp = requests_session.get(url)
        if resp.status_code == 200:
            data = resp.json()
            operator = data.get("OperatorFlagCode","") or data.get("Operator","")
            reg = data.get("Registration","")
            return operator.strip(), reg.strip()
    except Exception as e:
        print("hexdb error:", e)
    return "", ""

def lookup_planespotters(hex_code, requests_session):
    """Get operator for private/bizjet from planespotters.net - free, no key."""
    try:
        resp = requests_session.get(
            PLANESPOTTERS_URL + hex_code.upper(),
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            timeout=8
        )
        if resp.status_code == 200:
            ac = resp.json().get("aircraft", [])
            if ac:
                a = ac[0]
                operator = a.get("operator","") or a.get("airline",{}).get("name","")
                reg      = a.get("registration","")
                iata     = a.get("airline",{}).get("iata","")
                return operator.strip(), reg.strip(), iata.strip()
    except Exception as e:
        print("Planespotters:", e)
    return "", "", ""

def lookup_opensky(hex_code, requests_session):
    """Get operator/registration from OpenSky - free, no key."""
    try:
        resp = requests_session.get(OPENSKY_URL + hex_code.lower())
        if resp.status_code == 200:
            states = resp.json().get("states", [])
            if states:
                s = states[0]
                # [0]=icao24 [1]=callsign [2]=origin_country [7]=baroalt
                # [8]=onground [13]=squawk [14]=spi [15]=position_source
                callsign = (s[1] or "").strip()
                country  = s[2] or ""
                return callsign, country
    except Exception as e:
        print("OpenSky:", e)
    return "", ""

def enrich_from_adsb(hex_code, requests_session):
    """Fetch extra flight info from adsb.lol using ICAO hex"""
    try:
        resp = requests_session.get(ADSB_URL + hex_code.upper())
        if resp.status_code == 200:
            data = resp.json()
            ac = data.get("ac", [])
            if ac:
                a = ac[0]
                return {
                    "reg":       a.get("r",""),
                    "operator":  a.get("ownOp","") or a.get("man",""),
                    "origin":    a.get("orig",""),
                    "dest":      a.get("dest",""),
                    "flight":    a.get("flight","").strip(),
                    "aircraft":  a.get("t",""),
                    "alt":       a.get("alt_baro",0) or 0,
                    "speed":     a.get("gs",0) or 0,
                }
    except Exception as e:
        print("ADSB error:", e)
    return {}

WEATHER_CODES = {
    0:'Clear',1:'Mostly Clear',2:'Partly Cloudy',3:'Overcast',
    45:'Fog',48:'Fog',51:'Drizzle',53:'Drizzle',55:'Drizzle',
    61:'Light Rain',63:'Rain',65:'Heavy Rain',
    71:'Light Snow',73:'Snow',75:'Heavy Snow',
    80:'Showers',81:'Showers',82:'Heavy Showers',
    95:'Thunder',96:'Thunder',99:'Thunder',
}

COMP_NAMES = {
    'Premier League':'EPL','UEFA Champions League':'UCL',
    'UEFA Europa League':'UEL','UEFA Europa Conference League':'UECL',
    'UEFA Conference League':'UECL','Championship':'CHAMP',
    'FA Cup':'FA CUP','EFL Cup':'EFL CUP','Carabao Cup':'EFL CUP',
    'FIFA World Cup':'WORLDCUP','World Cup':'WORLDCUP',
    'UEFA European Championship':'EURO','UEFA Nations League':'UNL',
    'La Liga':'LA LIGA','Bundesliga':'BUNDES','Serie A':'SERIE A',
    'Ligue 1':'LIGUE 1','FIFA Club World Cup':'CLUB WC',
    'Copa America':'COPA','Copa América':'COPA',
    'Africa Cup of Nations':'AFCON','AFC Asian Cup':'ASIA CUP',
    'MLS':'MLS','Scottish Premiership':'SPL',
}

TEAM_COLOURS = {
    'West Ham United':0xB4182B,'West Ham':0xB4182B,
    'Arsenal':0xEF0107,'Chelsea':0x034694,'Liverpool':0xC8102E,
    'Manchester City':0x6CABDD,'Manchester United':0xDA291C,
    'Tottenham Hotspur':0x132257,'Tottenham':0x132257,
    'Newcastle United':0xAAAAAA,'Aston Villa':0x95BFE5,
    'Everton':0x003399,'Brighton':0x0057B8,'Wolves':0xFDB913,
    'Brentford':0xE30613,'Fulham':0xFFFFFF,
    'Nottingham Forest':0xDD0000,'Bournemouth':0xDA291C,
    'Crystal Palace':0x1B458F,'Southampton':0xD71920,
    'England':0xFFFFFF,'France':0x002395,'Germany':0xFFD700,
    'Spain':0xAA151B,'Italy':0x009246,'Brazil':0xFFDF00,
    'Argentina':0x74ACDF,'Netherlands':0xFF6600,'Portugal':0x006600,
    'Switzerland':0xFF0000,'Belgium':0xDD0000,
    'Real Madrid':0xFFFFFF,'Barcelona':0xA50044,
    'Bayern Munich':0xDC052D,'Bayern':0xDC052D,
    'Borussia Dortmund':0xFDE100,'Dortmund':0xFDE100,
    'PSG':0x004170,'Juventus':0xAAAAAA,
    'AC Milan':0xFB090B,'Inter Milan':0x010E80,'Inter':0x010E80,
}

def team_colour(name):
    for k,v in TEAM_COLOURS.items():
        if k.lower() in name.lower():
            return v
    return 0xFFFFFF

def short_name(name):
    codes = {
        'West Ham United':'WHU','West Ham':'WHU','Arsenal':'ARS',
        'Chelsea':'CHE','Liverpool':'LIV','Manchester City':'MCI',
        'Manchester United':'MNU','Tottenham Hotspur':'TOT','Tottenham':'TOT',
        'Newcastle United':'NEW','Aston Villa':'AVL','Everton':'EVE',
        'Brighton':'BHA','Wolves':'WOL','Brentford':'BRE','Fulham':'FUL',
        'Nottingham Forest':'NFO','Bournemouth':'BOU','Crystal Palace':'CPL',
        'Southampton':'SOU','Burnley':'BUR','Sheffield United':'SHU',
        'England':'ENG','France':'FRA','Germany':'GER','Spain':'ESP',
        'Italy':'ITA','Brazil':'BRA','Argentina':'ARG',
        'Netherlands':'NED','Portugal':'PRT','Belgium':'BEL',
        'Switzerland':'SUI','Croatia':'CRO','Denmark':'DEN',
        'Real Madrid':'RMA','Barcelona':'BAR','Bayern Munich':'BAY',
        'Bayern':'BAY','Borussia Dortmund':'BVB','Dortmund':'BVB',
        'PSG':'PSG','Juventus':'JUV','AC Milan':'MIL',
        'Inter Milan':'INT','Inter':'INT',
    }
    for k,v in codes.items():
        if k.lower() == name.lower():
            return v
    return name[:3].upper()

def comp_short(name):
    return COMP_NAMES.get(name, name[:8].upper())

def speed_to_delay(kts):
    if kts < 200: return 0.07
    if kts < 350: return 0.045
    if kts < 500: return 0.025
    return 0.015

def plane_colour_for(aircraft):
    a = aircraft.upper()
    if a.startswith('B') and len(a)==4: return 0xFFFFFF
    if a.startswith('A') and len(a)==4: return 0xFFD700
    return PLANE_COLOUR

# ---- Hardware ----
status_light = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.2)
matrixportal = MatrixPortal(headers=rheaders, rotation=0, debug=False)

_plane_speed_delay = 0.03
_plane_speed_knots = 0
_is_a380 = False
_current_airline = ''



# Airline livery: (fuselage_colour, tail_colour)
LIVERIES = {
    'SWR':  (0xFFFFFF, 0xFF0000),   # Swiss - white body red tail
    'OAW':  (0xFFFFFF, 0xFF0000),
    'DLH':  (0xFFFFFF, 0xFFCC00),   # Lufthansa - white body yellow tail
    'BAW':  (0xFFFFFF, 0x003399),   # BA - white body blue tail
    'EZY':  (0xFF6600, 0xFF6600),   # easyJet - all orange
    'RYR':  (0xFFFFFF, 0x003399),   # Ryanair - white body blue tail
    'AFR':  (0xFFFFFF, 0x002395),   # Air France - white body blue tail
    'KLM':  (0xFFFFFF, 0x00A1DE),   # KLM - white body light blue tail
    'UAE':  (0xFFFFFF, 0xCC0000),   # Emirates - white body red tail
    'THY':  (0xFFFFFF, 0xCC0000),   # Turkish - white body red tail
    'AUA':  (0xFFFFFF, 0xCC0000),   # Austrian - white body red tail
    'VLG':  (0xFFFF00, 0xFF6600),   # Vueling - yellow body orange tail
    'IBE':  (0xFFFFFF, 0xFF6600),   # Iberia - white body orange tail
    'EWG':  (0xFFFFFF, 0xCC00CC),   # Eurowings - white body purple tail
    'EDW':  (0xFFFFFF, 0xCC0000),   # Edelweiss - white body red tail
    'TAP':  (0xFFFFFF, 0x00AA44),   # TAP - white body green tail
    'SAS':  (0xFFFFFF, 0x003399),   # SAS - white body blue tail
    'WZZ':  (0xFF00CC, 0xFF00CC),   # Wizz - all magenta
    'TOM':  (0xFFFFFF, 0x00539B),   # TUI - white body blue tail
    'QTR':  (0xFFFFFF, 0x6C1D45),   # Qatar - white body maroon tail
    'SIA':  (0xFFFFFF, 0xFFD700),   # Singapore - white body gold tail
    'BTI':  (0x00AA00, 0x004400),   # airBaltic - green
    'SXS':  (0xFF6600, 0xFF0000),   # SunExpress - orange/red
    'BOM':  (0xFFFFFF, 0xCC0000),   # Helvetic - white body red tail
    # Scandinavian
    'FIN':  (0xFFFFFF, 0x003399),   # Finnair - white body blue tail
    'NAX':  (0xCC0000, 0xCC0000),   # Norwegian - red
    'BRA':  (0xFFFFFF, 0x006600),   # Braathens - white/green
    # Middle East / Asia
    'SVA':  (0x006600, 0x006600),   # Saudia - green
    'GFA':  (0xCC0000, 0x8B0000),   # Gulf Air - red/maroon
    'OMA':  (0xCC0000, 0x8B0000),   # Oman Air - red
    'MSR':  (0x003399, 0x003399),   # EgyptAir - blue
    'ELY':  (0xFFFFFF, 0x003399),   # El Al - white/blue
    'THA':  (0xFFFFFF, 0x6A0DAD),   # Thai - white/purple
    'MAS':  (0x003399, 0xCC0000),   # Malaysia - blue/red
    'SIA':  (0xFFFFFF, 0xFFD700),   # Singapore - white/gold
    'CPA':  (0xFFFFFF, 0x006600),   # Cathay - white/green
    'ANA':  (0xFFFFFF, 0x003399),   # ANA - white/blue
    'JAL':  (0xFFFFFF, 0xCC0000),   # JAL - white/red
    'KAL':  (0xFFFFFF, 0x003399),   # Korean Air - white/blue
    'AAR':  (0xFFFFFF, 0x00AAFF),   # Asiana - white/light blue
    'CCA':  (0xCC0000, 0xCC0000),   # Air China - red
    'CSN':  (0xFFFFFF, 0x003399),   # China Southern - white/blue
    'CES':  (0xFFFFFF, 0xCC0000),   # China Eastern - white/red
    'AIC':  (0xCC0000, 0xFF6600),   # Air India - red/orange
    # North America
    'AAL':  (0xFFFFFF, 0x003399),   # American - white/blue
    'UAL':  (0xFFFFFF, 0x003399),   # United - white/blue
    'DAL':  (0xFFFFFF, 0xCC0000),   # Delta - white/red
    'SWA':  (0xFF6600, 0xCC0000),   # Southwest - orange/red
    'JBU':  (0xFFFFFF, 0x0033A0),   # JetBlue - white/blue
    'WN':   (0xFF6600, 0xCC0000),   # Southwest - orange/red
    'ACA':  (0xCC0000, 0xCC0000),   # Air Canada - red
    'WJA':  (0xFFFFFF, 0x00AA44),   # WestJet - white/green
    # South America
    'LAN':  (0xFFFFFF, 0xCC0000),   # LATAM - white/red
    'TAM':  (0xFFFFFF, 0xCC0000),   # LATAM Brazil - white/red
    'AVA':  (0xCC0000, 0xFF6600),   # Avianca - red/orange
    'GLO':  (0xFF6600, 0xFF6600),   # Gol - orange
    # Africa / Other
    'ETH':  (0x006600, 0xFFD700),   # Ethiopian - green/gold
    'KQA':  (0xCC0000, 0x006600),   # Kenya Airways - red/green
    'SAA':  (0xFFFFFF, 0x003399),   # South African - white/blue
    'RAM':  (0x006600, 0xCC0000),   # Royal Air Maroc - green/red
    # Low cost Europe
    'VLG':  (0xFFFF00, 0xFF6600),   # Vueling - yellow/orange
    'VKG':  (0xFF6600, 0xFF6600),   # Thomas Cook - orange
    'CFG':  (0xFFFF00, 0xFFFF00),   # Condor - yellow
    'TRA':  (0x00AA44, 0x00AA44),   # Transavia - green
    'HV':   (0x00AA44, 0x00AA44),   # Transavia NL - green
    'TVS':  (0xFF6600, 0xFF6600),   # Smartwings - orange
    'CSE':  (0xFF0000, 0xFF0000),   # PrivatAir - red
    'LGL':  (0xFFFFFF, 0xCC0000),   # Luxair - white/red
    'AUA':  (0xFFFFFF, 0xCC0000),   # Austrian - white/red
}

def make_plane_bmp(airline=''):
    livery = LIVERIES.get(airline, (0xDDDDDD, PLANE_COLOUR))
    fuselage, tail = livery
    W,H = 40,20
    bmp = displayio.Bitmap(W,H,4)
    pal = displayio.Palette(4)
    pal[0]=0x000000; pal[1]=fuselage; pal[2]=tail; pal[3]=0x88CCFF
    def p(x,y,c):
        if 0<=x<W and 0<=y<H: bmp[x,y]=c
    def row(x1,x2,y,c):
        for x in range(x1,x2+1): p(x,y,c)
    # Tail fin - pointed
    p(0,0,2);
    row(0,1,1,2); row(0,2,2,2); row(0,3,3,2); row(0,4,3,2)
    row(0,4,5,2); row(0,4,6,2)
    # Fin base merges into fuselage
    row(0,4,7,2)
    # Fuselage top
    row(1,38,7,1)
    # Fuselage body
    row(0,38,8,1); row(0,38,9,1); row(0,38,10,1); row(0,38,11,1)
    # Fuselage bottom
    row(1,38,12,1)
    # Nose
    p(39,8,1); p(39,9,1); p(39,10,1); p(39,11,1)
    # Upper wing - wider triangle flush to fuselage top
    row(11,24,7,1)   # root at fuselage top
    row(9,22,6,1)
    row(8,20,5,1)
    row(7,18,4,1)
    row(7,15,3,1)
    row(7,13,2,1)
    row(7,10,1,1)
    p(7,0,1)
    # Lower wing - wider triangle flush to fuselage bottom
    row(11,24,12,1)  # root at fuselage bottom
    row(9,22,13,1)
    row(8,20,14,1)
    row(7,18,15,1)
    row(7,15,16,1)
    row(7,13,17,1)
    row(7,10,18,1)
    p(7,19,1)
    # Rear horizontal stabs
    row(0,7,13,2); row(0,6,14,2); row(0,4,15,2); row(1,3,16,2)
    # Windows
    for wx in [20,22,24,26,28,30,32,34,36]:
        p(wx,9,3)
    # Swiss cross on tail fin
    if airline in ('SWR','OAW'):
        pal[3] = 0xFFFFFF
        # Vertical bar of cross
        p(2,2,3); p(2,3,3); p(2,4,3); p(2,5,3)
        # Horizontal bar of cross
        p(1,3,3); p(2,3,3); p(3,3,3)
    return bmp,pal


def make_landing_bmp(airline=''):
    livery = LIVERIES.get(airline, (0xDDDDDD, PLANE_COLOUR))
    fuselage, tail = livery
    W,H = 40,20
    bmp = displayio.Bitmap(W,H,4)
    pal = displayio.Palette(4)
    pal[0]=0x000000; pal[1]=fuselage; pal[2]=tail; pal[3]=0x88CCFF
    def p(x,y,c):
        if 0<=x<W and 0<=y<H: bmp[x,y]=c
    def row(x1,x2,y,c):
        for x in range(x1,x2+1): p(x,y,c)
    # Mirror: tail fin on right side
    p(39,0,2)
    row(38,39,1,2); row(37,39,2,2); row(36,39,3,2); row(35,39,4,2)
    row(35,39,5,2); row(35,39,6,2); row(35,39,7,2)
    # Fuselage top
    row(1,38,7,1)
    # Fuselage body
    row(1,39,8,1); row(1,39,9,1); row(1,39,10,1); row(1,39,11,1)
    # Fuselage bottom
    row(1,38,12,1)
    # Nose on left
    p(0,8,1); p(0,9,1); p(0,10,1); p(0,11,1)
    # Upper wing (mirrored)
    row(15,28,7,1)
    row(17,30,6,1)
    row(19,31,5,1)
    row(21,32,4,1)
    row(24,32,3,1)
    row(26,32,2,1)
    row(29,32,1,1)
    p(32,0,1)
    # Lower wing (mirrored)
    row(15,28,12,1)
    row(17,30,13,1)
    row(19,31,14,1)
    row(21,32,15,1)
    row(24,32,16,1)
    row(26,32,17,1)
    row(29,32,18,1)
    p(32,19,1)
    # Rear stabs on right
    row(32,39,13,2); row(33,39,14,2); row(35,39,15,2); row(36,38,16,2)
    # Windows
    for wx in [3,5,7,9,11,13,15,17,19]:
        p(wx,9,3)
    # Swiss cross on tail fin (mirrored, tail is on right at x=35-39)
    if airline in ('SWR','OAW'):
        pal[3] = 0xFFFFFF
        p(37,2,3); p(37,3,3); p(37,4,3); p(37,5,3)
        p(36,3,3); p(37,3,3); p(38,3,3)
    return bmp,pal


def setup_plane(aircraft, speed_knots, airline=''):
    global _plane_speed_delay, _plane_speed_knots, _is_a380, _current_airline
    _plane_speed_delay = speed_to_delay(speed_knots)
    _plane_speed_knots = speed_knots
    _is_a380 = (aircraft.upper() == 'A388')
    _current_airline = airline

def make_anim_group(landing=False):
    bmp,pal = make_landing_bmp(_current_airline) if landing else make_plane_bmp(_current_airline)
    tg = displayio.TileGrid(bmp, pixel_shader=pal)
    spd = adafruit_display_text.label.Label(FONT,color=0xAAAAAA,text=str(_plane_speed_knots)+"kt")
    spd.x=1; spd.y=27
    pg = displayio.Group()
    pg.append(tg)
    pg.append(spd)
    return pg, tg

def plane_animation():
    pg, tg = make_anim_group(False)
    matrixportal.display.show(pg)
    tg.y = matrixportal.display.height//2 - 6
    for i in range(-40, matrixportal.display.width+40):
        tg.x=i; wfeed(); time.sleep(_plane_speed_delay)
    matrixportal.display.show(g)
    gc.collect()

def make_runway_bmp(width, side='left'):
    # Runway: 8px tall with tarmac, edge lines and centre dashes
    h = 8
    bmp = displayio.Bitmap(width, h, 4)
    pal = displayio.Palette(4)
    pal[0] = 0x000000  # black bg
    pal[1] = 0x444444  # dark grey tarmac
    pal[2] = 0xFFFFFF  # white edge lines
    pal[3] = 0xFFFF00  # yellow centre dashes
    # Tarmac fill
    for y in range(1, h):
        for x in range(width):
            bmp[x, y] = 1
    # White edge lines top and bottom of runway
    for x in range(width):
        bmp[x, 1] = 2
        bmp[x, h-1] = 2
    # Centre yellow dashes every 8px, 4px long
    cy = h // 2
    for x in range(0, width, 8):
        for dx in range(4):
            if x+dx < width:
                bmp[x+dx, cy] = 3
    # Threshold markers at start (takeoff) or end (landing)
    if side == 'left':
        for y in range(2, h-1, 2):
            for dx in range(3):
                if dx < width:
                    bmp[dx, y] = 2
    else:
        for y in range(2, h-1, 2):
            for dx in range(3):
                if width-1-dx >= 0:
                    bmp[width-1-dx, y] = 2
    return bmp, pal

def plane_animation_take_off():
    rw_bmp, rw_pal = make_runway_bmp(matrixportal.display.width, 'left')
    rw_tg = displayio.TileGrid(rw_bmp, pixel_shader=rw_pal, x=0, y=24)
    bmp, pal = make_plane_bmp(_current_airline)
    ptg = displayio.TileGrid(bmp, pixel_shader=pal)
    spd = adafruit_display_text.label.Label(FONT, color=0xAAAAAA, text=str(_plane_speed_knots)+"kt")
    spd.x=1; spd.y=4
    pg = displayio.Group()
    pg.append(rw_tg); pg.append(ptg); pg.append(spd)
    matrixportal.display.show(pg)
    steps = matrixportal.display.width+24
    for i in range(steps):
        ptg.x=-40+i
        ptg.y=8-(i*10//steps)
        wfeed(); time.sleep(_plane_speed_delay)
        if ptg.x>matrixportal.display.width or ptg.y<-20: break
    matrixportal.display.show(g)
    gc.collect()

def plane_animation_landing():
    rw_bmp, rw_pal = make_runway_bmp(matrixportal.display.width, 'right')
    rw_tg = displayio.TileGrid(rw_bmp, pixel_shader=rw_pal, x=0, y=24)
    bmp, pal = make_landing_bmp(_current_airline)
    ltg = displayio.TileGrid(bmp, pixel_shader=pal)
    spd = adafruit_display_text.label.Label(FONT, color=0xAAAAAA, text=str(_plane_speed_knots)+"kt")
    spd.x=1; spd.y=4
    pg = displayio.Group()
    pg.append(rw_tg); pg.append(ltg); pg.append(spd)
    matrixportal.display.show(pg)
    # Nose-first: enter upper-right, descend steeply to runway level lower-left
    steps = matrixportal.display.width + 40
    for i in range(steps):
        # x moves right to left: starts off right edge, ends off left edge
        ltg.x = matrixportal.display.width - i
        # y descends from -16 (above screen) to 12 (runway level)
        ltg.y = -16 + (i * 28 // steps)
        wfeed(); time.sleep(_plane_speed_delay)
        if ltg.x < -40 or ltg.y > 14: break
    matrixportal.display.show(g)
    gc.collect()

# ---- Labels ----
label1 = adafruit_display_text.label.Label(FONT,color=ROW_ONE_COLOUR,text="")
label1.x=1; label1.y=4
label2 = adafruit_display_text.label.Label(FONT,color=ROW_TWO_COLOUR,text="")
label2.x=1; label2.y=15
label3 = adafruit_display_text.label.Label(FONT,color=ROW_THREE_COLOUR,text="")
label3.x=1; label3.y=27

g = displayio.Group()
g.append(label1); g.append(label2); g.append(label3)
matrixportal.display.show(g)

label1_short=label1_long=label2_short=label2_long=label3_short=label3_long=''

def flap_in(label, target):
    target = target.upper()
    steps = [FLAP_CHARS.index(ch) if ch in FLAP_CHARS else 0 for ch in target]
    mx = max(steps) if steps else 0
    for step in range(mx+1):
        label.text = ''.join(FLAP_CHARS[min(step,s)] for s in steps)
        wfeed(); time.sleep(FLAP_SPEED)
    label.text = target

def scroll(line, restore_x):
    line.x = matrixportal.display.width
    for i in range(matrixportal.display.width+1, 0-line.bounding_box[2], -1):
        line.x=i; wfeed(); time.sleep(TEXT_SPEED)
    line.x = restore_x

def flap_all(t1, t2, t3):
    """Flap all three rows simultaneously"""
    t1 = t1.upper(); t2 = t2.upper(); t3 = t3.upper()
    s1 = [FLAP_CHARS.index(c) if c in FLAP_CHARS else 0 for c in t1]
    s2 = [FLAP_CHARS.index(c) if c in FLAP_CHARS else 0 for c in t2]
    s3 = [FLAP_CHARS.index(c) if c in FLAP_CHARS else 0 for c in t3]
    mx = max(max(s1) if s1 else 0, max(s2) if s2 else 0, max(s3) if s3 else 0)
    for step in range(mx+1):
        label1.text = ''.join(FLAP_CHARS[min(step,s)] for s in s1)
        label2.text = ''.join(FLAP_CHARS[min(step,s)] for s in s2)
        label3.text = ''.join(FLAP_CHARS[min(step,s)] for s in s3)
        wfeed(); time.sleep(FLAP_SPEED)
    label1.text=t1; label2.text=t2; label3.text=t3

def display_flight():
    matrixportal.display.show(g)
    label1.x=1; label2.x=1; label3.x=1
    # All three rows flap in simultaneously
    flap_all(label1_short, label2_short, label3_short)
    time.sleep(1)
    # Then scroll each long version in sequence
    label1.text=label1_long; scroll(label1,1); label1.text=label1_short; label1.x=1
    time.sleep(0.5)
    label2.text=label2_long; scroll(label2,1); label2.text=label2_short; label2.x=1
    time.sleep(0.5)
    label3.text=label3_long; scroll(label3,1); label3.text=label3_short; label3.x=1

def clear_flight():
    label1.text=label2.text=label3.text=""

def set_labels_from_feed(flight_info):
    global label1_short,label1_long,label2_short,label2_long,label3_short,label3_long
    callsign    = flight_info[13] or flight_info[16] or ''
    aircraft    = flight_info[8]  or ''
    origin      = flight_info[11] or ''
    destination = flight_info[12] or ''
    airline_icao= flight_info[18] if len(flight_info)>18 else ''
    speed_knots = flight_info[5]  if len(flight_info)>5  else 0

    setup_plane(aircraft, speed_knots, airline_icao)

    if aircraft.upper() in GA_TYPES:
        label1.color = GA_COLOUR
    elif airline_icao in AIRLINE_INFO:
        _,label1.color = AIRLINE_INFO[airline_icao]
    else:
        label1.color = COMMERCIAL_COLOUR

    label2.color = ROW_TWO_COLOUR
    label3.color = ROW_THREE_COLOUR

    # Enrich only what's actually missing - each API call costs ~1-2s
    hex_code = flight_info[0] if flight_info else ""
    adsb = {}
    needs_enrichment = hex_code and (not origin or not destination or not callsign)
    needs_operator   = hex_code and airline_icao not in AIRLINE_INFO

    if needs_enrichment:
        # adsb.lol - best single source, gets route + operator
        adsb = enrich_from_adsb(hex_code, requests_session)
        gc.collect()

    if needs_operator and not adsb.get("operator"):
        # Only hit planespotters if airline truly unknown (private jets etc)
        ps_op, ps_reg, _ = lookup_planespotters(hex_code, requests_session)
        if ps_op: adsb["operator"] = ps_op
        if ps_reg and not callsign: callsign = ps_reg
        gc.collect()

    # Fill gaps from ADS-B data
    if not origin and adsb.get("origin"):      origin      = adsb["origin"]
    if not destination and adsb.get("dest"):   destination = adsb["dest"]
    if not callsign and adsb.get("flight"):    callsign    = adsb["flight"]
    if not aircraft and adsb.get("aircraft"):  aircraft    = adsb["aircraft"]
    if not speed_knots and adsb.get("speed"):  speed_knots = int(adsb["speed"])

    if airline_icao in AIRLINE_INFO:
        airline_name = AIRLINE_INFO[airline_icao][0]
    elif adsb.get("operator"):
        airline_name = adsb["operator"][:12]
    else:
        airline_name = airline_icao
    orig_name,_  = AIRPORT_INFO.get(origin,(origin,''))
    dest_name,_  = AIRPORT_INFO.get(destination,(destination,''))
    aircraft_full= AIRCRAFT_NAMES.get(aircraft, aircraft)

    label1_short = callsign
    label1_long  = airline_name if airline_name != airline_icao else callsign
    label2_short = origin+'-'+destination if origin and destination else origin or destination
    label2_long  = orig_name+' - '+dest_name if orig_name and dest_name else orig_name or dest_name
    label3_short = aircraft
    label3_long  = aircraft_full
    print("Labels: "+callsign+" "+airline_name+" | "+origin+"-"+destination+" | "+aircraft_full+" | "+str(speed_knots)+"kt")

# ---- Weather ----
def temp_colour(temp):
    if temp<=0: return 0x0044FF
    if temp<=10: return 0x00CCFF
    if temp<=20: return 0x00FF88
    if temp<=28: return 0xFFCC00
    return 0xFF2200

def is_daytime(sunrise_str, sunset_str, current_time_str):
    """Compare HH:MM strings"""
    try:
        def to_mins(s):
            parts = s.split('T')[-1][:5].split(':')
            return int(parts[0])*60+int(parts[1])
        cur = to_mins(current_time_str)
        rise = to_mins(sunrise_str)
        sset = to_mins(sunset_str)
        return rise <= cur <= sset
    except:
        return True  # assume day if parse fails

def show_weather():
    try:
        resp = requests_session.get(WEATHER_URL)
        if resp.status_code==200:
            data = resp.json()
            cw   = data["current_weather"]
            temp = int(cw["temperature"])
            code = int(cw["weathercode"])
            wind = int(cw["windspeed"])
            ctime = cw.get("time","")
            cond = WEATHER_CODES.get(code,'Unknown')

            # Sunrise/sunset
            daily = data.get("daily",{})
            sunrise = daily.get("sunrise",[""])[0]
            sunset  = daily.get("sunset",[""])[0]
            day = is_daytime(sunrise, sunset, ctime)
            # After midday show sunset, before midday show sunrise
            try:
                cur_mins = int(ctime.split('T')[-1][:2])*60 + int(ctime.split('T')[-1][3:5])
                show_sunset = cur_mins >= 720
            except:
                show_sunset = not day

            # Sun/moon icon
            rise_str = sunrise.split('T')[-1][:5] if sunrise else ""
            sset_str = sunset.split('T')[-1][:5]  if sunset  else ""

            wg = displayio.Group()
            wl1 = adafruit_display_text.label.Label(FONT,color=temp_colour(temp),text=f"ZRH {temp}C")
            wl1.x=1; wl1.y=4
            wl2 = adafruit_display_text.label.Label(FONT,color=0xFFFFFF,text=cond[:10])
            wl2.x=1; wl2.y=15
            wl3 = adafruit_display_text.label.Label(FONT,color=0xFFAA00,
                text=("SET "+sset_str if show_sunset else "Up "+rise_str))
            wl3.x=1; wl3.y=26
            wg.append(wl1); wg.append(wl2); wg.append(wl3)
            matrixportal.display.show(wg)
            print("Weather: "+str(temp)+"C "+cond)
            for _ in range(20): wfeed(); time.sleep(0.5)
            matrixportal.display.show(g)
    except Exception as e:
        print("Weather error:", e)
    gc.collect()

# ---- Football ----
_last_scores = {}
_goal_queue  = []
# Competitions to always monitor
WATCHED_COMPS = ["PL","WC","EC","CL","UEL","UECL"]

# Teams we always want regardless of competition
PRIORITY_TEAMS = {
    "west ham","west ham united",
    "england",
    "fc aarau","aarau",
}

# Competitions where we only show semis/finals
SEMIS_FINALS_ONLY = {
    "serie a","coppa italia",
    "la liga","copa del rey",
    "ligue 1","coupe de france",
    "bundesliga","dfb-pokal",
    "super league","swiss cup",    # Swiss leagues
    "swiss super league",
}

# Competitions we always fully monitor
FULL_COVERAGE = {
    "premier league",
    "uefa champions league",
    "uefa europa league",
    "uefa europa conference league",
    "fifa world cup","world cup",
    "uefa european championship","euros",
    "uefa nations league",
    "fa cup","efl cup","carabao cup",
}

def should_show_match(home, away, comp_name, round_name=""):
    """Decide if we care about this match."""
    home_l = home.lower()
    away_l = away.lower()
    comp_l  = comp_name.lower()
    round_l = round_name.lower()

    # Always show priority team matches
    for team in PRIORITY_TEAMS:
        if team in home_l or team in away_l:
            return True

    # Always show full-coverage competitions
    for c in FULL_COVERAGE:
        if c in comp_l:
            return True

    # For semis/finals only competitions
    for c in SEMIS_FINALS_ONLY:
        if c in comp_l:
            if any(r in round_l for r in ("final","semi","halbfinale","semifinale","demi")):
                return True
            return False

    return False

def sofascore_to_match(event):
    """Convert Sofascore event to common match dict."""
    home = event.get("homeTeam",{})
    away = event.get("awayTeam",{})
    comp = event.get("tournament",{}).get("name","") or event.get("tournament",{}).get("uniqueTournament",{}).get("name","")
    status = event.get("status",{}).get("type","")
    score  = event.get("homeScore",{}), event.get("awayScore",{})
    minute = str(event.get("time",{}).get("played","") or "")
    fd_status = "IN_PLAY" if status in ("inprogress",) else ("PAUSED" if status=="pause" else "FINISHED")
    return {
        "id":          str(event.get("id","")),
        "status":      fd_status,
        "minute":      minute,
        "competition": {"name": comp},
        "homeTeam":    {"name": home.get("name",""), "shortName": home.get("nameCode","")},
        "awayTeam":    {"name": away.get("name",""), "shortName": away.get("nameCode","")},
        "score":       {"fullTime": {
            "home": score[0].get("current",0) or 0,
            "away": score[1].get("current",0) or 0,
        }},
        "stage": event.get("roundInfo",{}).get("name",""),
        "group": "",
        "_sofa_id": event.get("id",""),
    }

def fetch_live_matches():
    matches = []
    # Sofascore primary - no key needed
    sofa_ok = False
    try:
        resp = requests_session.get(SOFASCORE_LIVE, headers=SOFASCORE_HEADERS)
        if resp.status_code == 200:
            sofa_ok = True
            for event in resp.json().get("events", []):
                m    = sofascore_to_match(event)
                home = m["homeTeam"]["name"]
                away = m["awayTeam"]["name"]
                comp = m["competition"]["name"]
                rnd  = m["stage"]
                if should_show_match(home, away, comp, rnd):
                    matches.append(m)
        wfeed()
    except Exception as e:
        print(f"Sofascore: {e}")

    # football-data.org fallback if Sofascore failed and key exists
    if not sofa_ok and FOOTBALL_KEY:
        for comp in WATCHED_COMPS:
            try:
                url  = FOOTBALL_BASE+comp+"/matches?status=LIVE"
                resp = requests_session.get(url, headers=FOOTBALL_HEADERS)
                if resp.status_code==200:
                    for m in resp.json().get("matches",[]):
                        home = m.get("homeTeam",{}).get("name","")
                        away = m.get("awayTeam",{}).get("name","")
                        comp_name = m.get("competition",{}).get("name","")
                        rnd  = m.get("stage","")
                        if should_show_match(home, away, comp_name, rnd):
                            matches.append(m)
                wfeed()
            except Exception as e:
                print(f"FD {comp}: {e}")
    return matches


def check_for_goals(matches):
    global _last_scores, _goal_queue
    for m in matches:
        status = m.get("status","")
        if status not in ("IN_PLAY","PAUSED"):
            continue
        mid  = str(m.get("id",""))
        home = m.get("homeTeam",{}).get("shortName") or m.get("homeTeam",{}).get("name","?")
        away = m.get("awayTeam",{}).get("shortName") or m.get("awayTeam",{}).get("name","?")
        ft   = m.get("score",{}).get("fullTime",{})
        hs   = ft.get("home") or 0
        aws  = ft.get("away") or 0
        minute = str(m.get("minute",""))
        comp = m.get("competition",{}).get("name","")
        if mid not in _last_scores:
            _last_scores[mid]=(hs,aws); continue
        ph,pa = _last_scores[mid]
        if hs>ph or aws>pa:
            scorer = get_scorer(home, away)
        if hs>ph:
            _goal_queue.append({"comp":comp,"home":home,"away":away,"hs":hs,"aws":aws,"scorer":scorer,"minute":minute,"team":home})
        if aws>pa:
            _goal_queue.append({"comp":comp,"home":home,"away":away,"hs":hs,"aws":aws,"scorer":scorer,"minute":minute,"team":away})
        _last_scores[mid]=(hs,aws)

def display_score(goal):
    home = goal["home"]; away = goal["away"]
    hs=str(goal["hs"]); aws=str(goal["aws"])
    comp=comp_short(goal.get("comp",""))
    sh=short_name(home); sa=short_name(away)
    scoring_team=goal.get("team",home)
    score_on  = sh+hs+"-"+aws+sa
    score_off = sh+" "*len(hs)+"-"+" "*len(aws)+sa
    is_home = scoring_team.lower()==home.lower()
    matrixportal.display.show(g)
    label1.color=0xFFCC00; label1.x=1; label1.text=comp
    label2.color=0xFFFFFF; label2.x=1; label2.text=score_on
    label3.color=0x00FF00; label3.x=1
    label3.text = (goal.get("scorer","") or "GOAL!") + (" "+goal["minute"]+"'" if goal["minute"] else "")
    scorer_text = label3.text
    for i in range(16):
        label3.text = scorer_text if i%2==0 else ""
        wfeed(); time.sleep(0.5)
    label1.color=ROW_ONE_COLOUR; label2.color=ROW_TWO_COLOUR; label3.color=ROW_THREE_COLOUR
    gc.collect()

def show_live_scores(matches):
    if not matches: return
    matrixportal.display.show(g)
    for m in matches[:4]:
        home=(m.get("homeTeam",{}).get("shortName") or m.get("homeTeam",{}).get("name","?"))
        away=(m.get("awayTeam",{}).get("shortName") or m.get("awayTeam",{}).get("name","?"))
        ft=m.get("score",{}).get("fullTime",{})
        hs=ft.get("home",0) or 0; aws=ft.get("away",0) or 0
        minute=str(m.get("minute",""))
        comp=comp_short(m.get("competition",{}).get("name",""))
        label1.color=0xFFCC00; label1.text=comp; label1.x=1
        label2.color=0xFFFFFF; label2.text=short_name(home)+str(hs)+"-"+str(aws)+short_name(away); label2.x=1
        label3.color=0xAAAAAA; label3.text=minute+"'" if minute else "Live"; label3.x=1
        for _ in range(6): wfeed(); time.sleep(0.5)
    label1.color=ROW_ONE_COLOUR; label2.color=ROW_TWO_COLOUR; label3.color=ROW_THREE_COLOUR
    clear_flight()

# ---- Flights ----
# Cricket state tracking
_cricket_last    = {}
_cricket_match_id   = None
_cricket_series_id  = None

def cricinfo_get(path):
    try:
        url  = CRICINFO_BASE + path
        resp = requests_session.get(url, headers=CRICINFO_HEADERS)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print("Cricinfo:", e)
    return None

def find_england_match():
    """Search current matches for England."""
    global _cricket_match_id, _cricket_series_id
    data = cricinfo_get("/matches/current?lang=en&fixture=false")
    if not data:
        return None
    for match in data.get("matches", []):
        teams = [t.get("longName","").lower() for t in match.get("teams",[])]
        if any("england" in t for t in teams):
            _cricket_match_id  = match.get("objectId")
            _cricket_series_id = match.get("series",{}).get("objectId")
            print("Cricket match: "+str(_cricket_match_id))
            return match
    return None

def get_match_summary():
    """Get live match summary using cached IDs."""
    if not _cricket_match_id:
        return None
    path = f"/match/summary?lang=en&matchId={_cricket_match_id}"
    if _cricket_series_id:
        path += f"&seriesId={_cricket_series_id}"
    return cricinfo_get(path)

def get_match_scorecard():
    """Get full scorecard."""
    if not _cricket_match_id:
        return None
    path = f"/match/scorecard?lang=en&matchId={_cricket_match_id}"
    if _cricket_series_id:
        path += f"&seriesId={_cricket_series_id}"
    return cricinfo_get(path)

def cricket_hold(secs=6):
    for _ in range(secs*2):
        wfeed(); time.sleep(0.5)

def show_cricket_screen(l1c,l1t, l2c,l2t, l3c,l3t, secs=5):
    matrixportal.display.show(g)
    label1.color=l1c; label1.x=1; label1.text=l1t[:10]
    label2.color=l2c; label2.x=1; label2.text=l2t[:10]
    label3.color=l3c; label3.x=1; label3.text=l3t[:10]
    cricket_hold(secs)

def scroll_cricket_text(text, colour, label):
    label.color = colour; label.text = text
    label.x = matrixportal.display.width
    for i in range(matrixportal.display.width+1, 0-label.bounding_box[2], -1):
        label.x=i; wfeed(); time.sleep(TEXT_SPEED)
    label.x=1

def parse_innings(summary):
    """Extract current innings info from summary."""
    try:
        innings_list = summary.get("match",{}).get("innings",[])
        if not innings_list:
            return None
        inn = innings_list[-1]
        return {
            "team":   inn.get("team",{}).get("abbreviation","???"),
            "runs":   inn.get("runs", 0),
            "wkts":   inn.get("wickets", 0),
            "overs":  inn.get("overs",""),
            "inn_num":len(innings_list),
        }
    except:
        return None

def display_cricket_wicket(summary, scorecard, prev_wkts):
    """Show WICKET alert with dismissal details."""
    inn = parse_innings(summary)
    if not inn:
        return
    team  = inn["team"]
    runs  = inn["runs"]
    wkts  = inn["wkts"]
    overs = inn["overs"]

    # Find dismissed batsman from scorecard
    dismissed = ""; bowler = ""; fielder = ""; b_runs = 0
    if scorecard:
        try:
            for innings in scorecard.get("scorecard",[]):
                if innings.get("inningNumber") == inn["inn_num"]:
                    for b in innings.get("batting",[]):
                        dism = b.get("dismissalText",{})
                        if dism.get("long","").lower() not in ("","not out","batting","yet to bat"):
                            dismissed = b.get("player",{}).get("shortName","").split()[-1]
                            b_runs    = b.get("runs",0)
                            balls     = b.get("balls",0)
                            # bowler and fielder from dismissal
                            bl = b.get("bowler",{}).get("shortName","").split()[-1]
                            fi = b.get("fielder",{}).get("shortName","").split()[-1] if b.get("fielder") else ""
                            bowler  = bl
                            fielder = fi
                            break
        except:
            pass

    matrixportal.display.show(g)
    # Flash WICKET
    for _ in range(4):
        label1.color=0xFF0000; label1.text="WICKET!"; label1.x=1
        label2.color=0xFFFFFF; label2.text=f"{team} {wkts}/{runs}"
        label3.color=0xAAAAAA; label3.text=f"Ov {overs}"
        wfeed(); time.sleep(0.35)
        label1.text=""; wfeed(); time.sleep(0.25)
    label1.text="WICKET!"
    cricket_hold(3)

    if dismissed:
        b_str = f"{dismissed} {b_runs}({balls})"
        show_cricket_screen(
            0xFF0000,"WICKET!",
            0xFFFFFF,f"{team} {wkts}/{runs}",
            0xFFAA00,b_str, secs=4
        )
        if bowler:
            d_str = f"b.{bowler}"
            if fielder:
                d_str += f" c.{fielder}"
            scroll_cricket_text(d_str, 0xAAAAAA, label3)
    gc.collect()

def display_cricket_innings_end(summary, scorecard):
    """End of innings summary - score, top 3 bat, top 3 bowl."""
    inn = parse_innings(summary)
    if not inn:
        return
    team  = inn["team"]
    runs  = inn["runs"]
    wkts  = inn["wkts"]
    overs = inn["overs"]

    show_cricket_screen(
        0xFFFF00,"INNINGS",
        0xFFFFFF,f"{team} {wkts}/{runs}",
        0xAAAAAA,f"Overs {overs}", secs=5
    )

    if not scorecard:
        return

    try:
        for innings in scorecard.get("scorecard",[]):
            if innings.get("inningNumber") != inn["inn_num"]:
                continue

            # Top 3 batters by runs
            batters = sorted(innings.get("batting",[]),
                           key=lambda x: x.get("runs",0), reverse=True)[:3]
            for b in batters:
                name  = b.get("player",{}).get("shortName","").split()[-1][:7]
                r     = b.get("runs",0)
                balls = b.get("balls",0)
                show_cricket_screen(
                    0x00FF88,"BATTING",
                    0xFFFFFF,f"{name} {r}({balls})",
                    0xAAAAAA,"", secs=4
                )

            # Top 3 bowlers by wickets
            bowlers = sorted(innings.get("bowling",[]),
                           key=lambda x: (x.get("wickets",0),-x.get("conceded",999)),
                           reverse=True)[:3]
            for b in bowlers:
                name  = b.get("player",{}).get("shortName","").split()[-1][:7]
                wk    = b.get("wickets",0)
                conc  = b.get("conceded",0)
                ov    = b.get("overs","")
                show_cricket_screen(
                    0xFF6600,"BOWLING",
                    0xFFFFFF,f"{name} {wk}/{conc}",
                    0xAAAAAA,f"Ov {ov}", secs=4
                )
    except Exception as e:
        print("Innings end:", e)
    gc.collect()

def display_cricket_result(summary):
    """Match result display."""
    try:
        match  = summary.get("match",{})
        result = match.get("statusText","") or match.get("result",{}).get("winnerTeam",{}).get("longName","")
        innings_list = match.get("innings",[])
        teams  = [i.get("team",{}).get("abbreviation","?") for i in innings_list[:2]]
        scores = [f"{i.get('runs',0)}/{i.get('wickets',0)}" for i in innings_list[:2]]

        t1 = teams[0] if teams else "?"
        t2 = teams[1] if len(teams)>1 else "?"
        s1 = scores[0] if scores else "-"
        s2 = scores[1] if len(scores)>1 else "-"

        show_cricket_screen(
            0xFFFF00,"RESULT",
            0xFFFFFF,f"{t1} {s1}",
            0xAAAAAA,f"{t2} {s2}", secs=5
        )
        if result:
            scroll_cricket_text(result[:40], 0x00FF88, label2)
    except Exception as e:
        print("Result:", e)
    gc.collect()

def display_cricket_score(summary):
    """Routine score update."""
    inn = parse_innings(summary)
    if not inn:
        return
    # Previous innings
    innings_list = summary.get("match",{}).get("innings",[])
    prev = ""
    if len(innings_list) > 1:
        p = innings_list[-2]
        pt = p.get("team",{}).get("abbreviation","?")
        prev = f"{pt} {p.get('runs',0)}/{p.get('wickets',0)}"
    show_cricket_screen(
        0x00AAFF,"CRICKET",
        0xFFFFFF,f"{inn['team']} {inn['wkts']}/{inn['runs']}",
        0xAAAAAA,f"Ov {inn['overs']} {prev}", secs=5
    )

def process_cricket():
    """Main cricket handler."""
    global _cricket_last, _cricket_match_id

    # Find match if we don't have one
    if not _cricket_match_id:
        find_england_match()
    if not _cricket_match_id:
        return

    summary = get_match_summary()
    if not summary:
        _cricket_match_id = None  # reset, will rediscover
        return

    match   = summary.get("match",{})
    mid     = str(_cricket_match_id)
    status  = match.get("state","")
    last    = _cricket_last.get(mid, {})

    # Match over
    if status in ("complete","post"):
        if not last.get("ended"):
            scorecard = get_match_scorecard()
            display_cricket_result(summary)
            if scorecard:
                display_cricket_innings_end(summary, scorecard)
            _cricket_last[mid] = {"ended": True}
        return

    # In progress
    inn = parse_innings(summary)
    if not inn:
        return

    curr_wkts = inn["wkts"]
    curr_inn  = inn["inn_num"]
    prev_wkts = last.get("wkts", curr_wkts)
    prev_inn  = last.get("inn_num", curr_inn)

    if curr_wkts > prev_wkts:
        scorecard = get_match_scorecard()
        display_cricket_wicket(summary, scorecard, prev_wkts)
        if curr_wkts >= 10:
            display_cricket_innings_end(summary, scorecard)
    elif curr_inn > prev_inn and prev_inn > 0:
        scorecard = get_match_scorecard()
        display_cricket_innings_end(summary, scorecard)
    else:
        display_cricket_score(summary)

    _cricket_last[mid] = {
        "wkts":    curr_wkts,
        "inn_num": curr_inn,
        "ended":   False,
    }

    label1.color = ROW_ONE_COLOUR
    label2.color = ROW_TWO_COLOUR
    label3.color = ROW_THREE_COLOUR
def get_flights(url, headers):
    print("Starting get_flights function")
    try:
        resp = requests_session.get(url, headers=headers)
        if resp.status_code==200:
            data = resp.json(); print(data)
            flights=[]; raw={}
            for fid,fi in data.items():
                if fid not in ("version","full_count") and len(fi)>13:
                    o=fi[11]; d=fi[12]
                    if o and d:
                        flights.append((fid,o,d)); raw[fid]=fi
                    else:
                        print("Skip "+fid)
            return flights,raw
        print("Flight API error:", resp.status_code)
        return [],{}
    except Exception as e:
        print("Flight error:", e); return [],{}

# ---- Main loop ----
last_flight=''; sports_cycle=0
SPORTS_EVERY=2

while True:
    checkConnection()
    wfeed()
    print("memory free: "+str(gc.mem_free()))

    sports_cycle+=1
    if sports_cycle>=SPORTS_EVERY:
        sports_cycle=0
        if ENABLE_FOOTBALL:
            try:
                live=fetch_live_matches()
                check_for_goals(live)
                while _goal_queue:
                    display_score(_goal_queue.pop(0)); wfeed()
                if live: show_live_scores(live)
            except Exception as e:
                print("Sports error:", e)
        if ENABLE_CRICKET:
            try:
                process_cricket()
            except Exception as e:
                print("Cricket error:", e)

    wfeed()
    if ENABLE_FLIGHTS:
        flights,raw = get_flights(FLIGHT_URL, rheaders)
        if flights:
            for fid,origin,dest in flights:
                if fid!=last_flight:
                    print("New flight "+fid)
                    clear_flight(); last_flight=fid; gc.collect()
                    fi=raw.get(fid)
                    if fi:
                        set_labels_from_feed(fi)
                        if origin==HOME_AIRPORT: plane_animation_take_off()
                        elif dest==HOME_AIRPORT: plane_animation_landing()
                        else: plane_animation()
                        display_flight()
        elif ENABLE_WEATHER:
            show_weather()
    elif ENABLE_WEATHER:
        show_weather()

    time.sleep(5)
    for _ in range(0,QUERY_DELAY,5):
        time.sleep(5); wfeed()
    gc.collect()