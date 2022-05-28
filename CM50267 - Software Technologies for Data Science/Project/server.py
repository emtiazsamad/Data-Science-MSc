#!/usr/bin/env python

# This is a simple web server for a traffic counting application.
# It's your job to extend it by adding the backend functionality to support
# recording the traffic in a SQL database. You will also need to support
# some predefined users and access/session control. You should only
# need to extend this file. The client side code (html, javascript and css)
# is complete and does not require editing or detailed understanding.

# import the various libraries needed
import http.cookies as Cookie # some cookie handling support
from http.server import BaseHTTPRequestHandler, HTTPServer # the heavy lifting of the web server
import urllib # some url parsing support
import json # support for json encoding
import sys # needed for agument handling

import sqlite3
import time
import math
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


def build_response_refill(where, what):
    """This function builds a refill action that allows part of the
       currently loaded page to be replaced."""
    return {"type":"refill","where":where,"what":what}


def build_response_redirect(where):
    """This function builds the page redirection action
       It indicates which page the client should fetch.
       If this action is used, only one instance of it should
       contained in the response and there should be no refill action."""
    return {"type":"redirect", "where":where}

def access_database(dbfile, query):
    '''Function does not return result of query'''
    connect = sqlite3.connect(dbfile)
    cursor = connect.cursor()
    cursor.execute(query)
    connect.commit()
    connect.close()

def access_database_with_result(dbfile, query):
    '''Function returns result of query'''
    connect = sqlite3.connect(dbfile)
    cursor = connect.cursor()
    rows = cursor.execute(query).fetchall()
    connect.commit()
    connect.close()
    return rows

def handle_validate(iuser, imagic):
    """Decide if the combination of user and magic is valid"""

    combination = access_database_with_result('traffic.db',
        f"SELECT * FROM users INNER JOIN session ON users.userid = session.userid \
            WHERE users.username = '{iuser}' AND session.magic = '{imagic}' AND session.end = 0")
    if len(combination) > 0:
        return True
    else:
        return False

def handle_delete_session(iuser, imagic):
    """Remove the combination of user and magic from the data base, ending the login"""
    user = '!'
    magic = ''
    return user, magic

def handle_login_request(iuser, imagic, parameters):
    """A user has supplied a username (parameters['usernameinput'][0])
       and password (parameters['passwordinput'][0]) check if these are
       valid and if so, create a suitable session record in the database
       with a random magic identifier that is returned.
       Return the username, magic identifier and the response action set."""
    response = []

    if handle_validate(iuser, imagic) == True:
        # the user is already logged in, so end the existing session.
        handle_delete_session(iuser, imagic)
    try:
        output = access_database_with_result('traffic.db', \
            f"SELECT * FROM users WHERE username = '{parameters['usernameinput'][0]}' \
                AND password = '{parameters['passwordinput'][0]}'")
        if len(output) > 0:
            user = parameters['usernameinput'][0]
            magic = parameters['randn'][0]
            start_time = int(time.time())
            end_time = 0
            response.append(build_response_redirect('/page.html'))
            access_database_with_result('traffic.db', f"UPDATE session SET end = '{start_time}' \
                WHERE userid = '{output[0][0]}' AND end = 0")
            access_database('traffic.db', f"INSERT INTO session (userid, magic, start, end) \
                VALUES ('{output[0][0]}', '{magic}', '{start_time}', '{end_time}')")

        else: ## The user is not valid
            response.append(build_response_refill('message', 'Invalid credentials'))
            user = '!'
            magic = ''
    except KeyError: ## username and/ or password field(s) is empty
        response.append(build_response_refill('message', 'Please fill in all fields'))
        user = '!'
        magic = ''
    return [user, magic, response]

def handle_add_request(iuser, imagic, parameters):
    """The user has requested a vehicle be added to the count
       parameters['locationinput'][0] the location to be recorded
       parameters['occupancyinput'][0] the occupant count to be recorded
       parameters['typeinput'][0] the type to be recorded
       Return the username, magic identifier (these can be empty  strings)
       and the response action set."""
    response = []
    ## alter as required
    if handle_validate(iuser, imagic) != True:
        #Invalid sessions redirect to login
        response.append(build_response_redirect('/index.html'))
        user = '!'
        magic = ''
    else: ## a valid session so process the addition of the entry.

        s_id = access_database_with_result('traffic.db', f"SELECT sessionid \
            FROM session WHERE magic = '{imagic}'")[0][0]
        record_time = int(time.time())
        vehicle = {"car": 0, "van":1, "truck":2, "taxi":3, "other":4, \
            "motorbike":5, "bicycle":6, "bus":7}

        try:
            str(parameters['locationinput'][0])
        except KeyError:
            response.append(build_response_refill('message', 'Enter location'))
            user = ''
            magic = ''
            return [user, magic, response]

        if all(x.isalnum() or x.isspace() for x in str(parameters['locationinput'][0])) \
            and len([x for x in str(parameters['locationinput'][0]) if x.islower()]) > 0 \
                and len([x for x in str(parameters['locationinput'][0]) if x.isupper()]) < 1:
            pass
        else:
            response.append(build_response_refill('message', \
                'Invalid location - must contain at least one lowercase \
                    letter and can also include integers'))
            user = ''
            magic = ''
            return [user, magic, response]
        try:
            vehicle[parameters['typeinput'][0]]
        except KeyError:
            response.append(build_response_refill('message', 'Vehicle not recognised'))
            user = ''
            magic = ''
            return [user, magic, response]
        try:
            [1,2,3,4].index(int(parameters['occupancyinput'][0]))
        except ValueError:
            response.append(build_response_refill('message', 'Passengar count not in valid range'))
            user = ''
            magic = ''
            return [user, magic, response]
        if parameters['typeinput'][0] in vehicle.keys() and \
            (0 < int(parameters['occupancyinput'][0]) <= 4):
            access_database('traffic.db', f"INSERT INTO traffic \
                                            (sessionid, time, type, occupancy, location, mode) \
                                            VALUES('{s_id}', '{record_time}', '{vehicle[parameters['typeinput'][0]]}', '{int(parameters['occupancyinput'][0])}', '{str(parameters['locationinput'][0])}', 1)")
            response.append(build_response_refill('message', 'Entry added'))
            add_count = access_database_with_result('traffic.db', \
                f"SELECT COUNT(recordid) FROM traffic \
                    WHERE sessionid = '{s_id}' AND mode BETWEEN 1 AND 2")
            remove_count = access_database_with_result('traffic.db', \
                f"SELECT COUNT(recordid) FROM traffic WHERE sessionid = '{s_id}' AND mode = 0")
            response.append(build_response_refill('total', \
                str(add_count[0][0] - remove_count[0][0])))
            user = iuser
            magic = imagic
    return [user, magic, response]

def handle_undo_request(iuser, imagic, parameters):
    """The user has requested a vehicle be removed from the count
       This is intended to allow counters to correct errors.
       parameters['locationinput'][0] the location to be recorded
       parameters['occupancyinput'][0] the occupant count to be recorded
       parameters['typeinput'][0] the type to be recorded
       Return the username, magic identifier (these can be empty  strings)
       and the response action set."""
    response = []
    ## alter as required
    if handle_validate(iuser, imagic) != True:
        #Invalid sessions redirect to login
        response.append(build_response_redirect('/index.html'))
    else: ## a valid session so process the recording of the entry.

        s_id = access_database_with_result('traffic.db', \
            f"SELECT sessionid FROM session WHERE magic = '{imagic}'")[0][0]
        vehicle = {"car": 0, "van":1, "truck":2, "taxi":3, "other":4, "motorbike":5, "bicycle":6, "bus":7}
        try:
            str(parameters['locationinput'][0])
        except KeyError:
            response.append(build_response_refill('message', 'Enter location'))
            user = ''
            magic = ''
            return [user, magic, response]
        if all(x.isalnum() or x.isspace() for x in str(parameters['locationinput'][0])) and len([x for x in str(parameters['locationinput'][0]) if x.islower()]) > 0 and len([x for x in str(parameters['locationinput'][0]) if x.isupper()]) < 1:
            pass
        else:
            response.append(build_response_refill('message', \
                'Invalid location - must contain at least one lowercase letter and can also include integers'))
            user = ''
            magic = ''
            return [user, magic, response]

        try:
            vehicle[parameters['typeinput'][0]]
        except KeyError:
            response.append(build_response_refill('message', 'Vehicle not recognised'))
            user = ''
            magic = ''
            return [user, magic, response]
        try:
            [1,2,3,4].index(int(parameters['occupancyinput'][0]))
        except ValueError:
            response.append(build_response_refill('message', 'Passengar count not in valid range'))
            user = ''
            magic = ''
            return [user, magic, response]
        if parameters['typeinput'][0] in vehicle.keys() and \
            (1 <= int(parameters['occupancyinput'][0]) <= 4):
            if len(access_database_with_result('traffic.db', f"SELECT * FROM traffic WHERE mode = 1 \
                                                AND sessionid = '{s_id}' AND type = '{vehicle[parameters['typeinput'][0]]}' \
                                                AND occupancy = '{parameters['occupancyinput'][0]}' AND \
                                                location = '{parameters['locationinput'][0]}'")) == 0:
                response.append(build_response_refill('message', 'No such record exists'))

            else:
                access_database('traffic.db', f"INSERT INTO traffic \
                    (sessionid, time, type, occupancy, location, mode) \
                                                SELECT sessionid, time, type, occupancy, location, '0' FROM traffic \
                                                WHERE mode = 1 AND sessionid = '{s_id}' AND type = '{vehicle[parameters['typeinput'][0]]}' \
                                                AND occupancy = '{parameters['occupancyinput'][0]}' AND location = '{parameters['locationinput'][0]}' \
                                                ORDER BY recordid DESC \
                                                LIMIT 1")
                access_database_with_result('traffic.db', f"UPDATE traffic SET mode = 2 WHERE recordid = (SELECT MAX(recordid) FROM traffic WHERE mode = 1 \
                                                            AND sessionid = '{s_id}' AND type = '{vehicle[parameters['typeinput'][0]]}' \
                                                            AND occupancy = '{parameters['occupancyinput'][0]}' AND location = '{parameters['locationinput'][0]}')")
                response.append(build_response_refill('message', 'Entry removed'))
            add_count = access_database_with_result('traffic.db', \
                f"SELECT COUNT(recordid) FROM traffic \
                    WHERE sessionid = '{s_id}' AND mode BETWEEN 1 AND 2")
            remove_count = access_database_with_result('traffic.db', \
                f"SELECT COUNT(recordid) FROM traffic WHERE sessionid = '{s_id}' AND mode = 0")
            response.append(build_response_refill('total', \
                str(add_count[0][0] - remove_count[0][0])))
            user = iuser
            magic = imagic
    return [user, magic, response]

def handle_back_request(iuser, imagic, parameters):
    """This code handles the selection of the back button on the record form (page.html)
       You will only need to modify this code if you make changes elsewhere that 
       break its behaviour"""
    response = []
    ## alter as required
    if handle_validate(iuser, imagic) != True:
        response.append(build_response_redirect('/index.html'))
    else:
        response.append(build_response_redirect('/summary.html'))
    user = ''
    magic = ''
    return [user, magic, response]


def handle_logout_request(iuser, imagic, parameters):
    """This code handles the selection of the logout button on the summary page (summary.html)
       You will need to ensure the end of the session is recorded in the database
       And that the session magic is revoked."""
    response = []
    if handle_validate(iuser, imagic) != True:
        #Invalid sessions redirect to login
        response.append(build_response_redirect('/index.html'))
        user = '!'
        magic = ''
    else:
    ## alter as required
        s_id = access_database_with_result('traffic.db', \
            f"SELECT sessionid FROM session WHERE magic = '{imagic}'")[0][0]
        end_time = int(time.time())
        access_database_with_result('traffic.db', \
            f"UPDATE session SET end = '{end_time}' WHERE sessionid = '{s_id}' AND end = 0")
        response.append(build_response_redirect('/index.html'))
        user = '!'
        magic = ''
    return [user, magic, response]


def handle_summary_request(iuser, imagic, parameters):
    """This code handles a request for an update to the session summary values.
       You will need to extract this information from the database.
       You must return a value for all vehicle types, even when it's zero."""
    response = []
    s_id = access_database_with_result('traffic.db', f"SELECT sessionid FROM session WHERE magic = '{imagic}'")[0][0]
    add_count = access_database_with_result('traffic.db', f"SELECT COUNT(recordid) FROM traffic WHERE sessionid = '{s_id}' AND mode BETWEEN 1 AND 2")
    remove_count = access_database_with_result('traffic.db', f"SELECT COUNT(recordid) FROM traffic WHERE sessionid = '{s_id}' AND mode = 0")
    sum_car = access_database_with_result('traffic.db', f"SELECT COUNT(recordid) FROM traffic WHERE sessionid = '{s_id}' AND type = 0 AND mode = 1")
    sum_van = access_database_with_result('traffic.db', f"SELECT COUNT(recordid) FROM traffic WHERE sessionid = '{s_id}' AND type = 1 AND mode = 1")
    sum_truck = access_database_with_result('traffic.db', f"SELECT COUNT(recordid) FROM traffic WHERE sessionid = '{s_id}' AND type = 2 AND mode = 1")
    sum_taxi = access_database_with_result('traffic.db', f"SELECT COUNT(recordid) FROM traffic WHERE sessionid = '{s_id}' AND type = 3 AND mode = 1")
    sum_other = access_database_with_result('traffic.db', f"SELECT COUNT(recordid) FROM traffic WHERE sessionid = '{s_id}' AND type = 4 AND mode = 1")
    sum_motorbike = access_database_with_result('traffic.db', f"SELECT COUNT(recordid) FROM traffic WHERE sessionid = '{s_id}' AND type = 5 AND mode = 1")
    sum_bicycle = access_database_with_result('traffic.db', f"SELECT COUNT(recordid) FROM traffic WHERE sessionid = '{s_id}' AND type = 6 AND mode = 1")
    sum_bus = access_database_with_result('traffic.db', f"SELECT COUNT(recordid) FROM traffic WHERE sessionid = '{s_id}' AND type = 7 AND mode = 1")
    ## alter as required
    if handle_validate(iuser, imagic) != True:
        response.append(build_response_redirect('/index.html'))
    else:
        response.append(build_response_refill('sum_car', sum_car))
        response.append(build_response_refill('sum_taxi', sum_taxi))
        response.append(build_response_refill('sum_bus', sum_bus))
        response.append(build_response_refill('sum_motorbike', sum_motorbike))
        response.append(build_response_refill('sum_bicycle', sum_bicycle))
        response.append(build_response_refill('sum_van', sum_van))
        response.append(build_response_refill('sum_truck', sum_truck))
        response.append(build_response_refill('sum_other', sum_other))
        response.append(build_response_refill('total', str(add_count[0][0] - remove_count[0][0])))
        user = ''
        magic = ''
    return [user, magic, response]

def db_csv_traffic():

    last_record = access_database_with_result('traffic.db', \
        'SELECT MAX(time) FROM traffic WHERE mode = 1')[0][0]
    last_record = datetime.fromtimestamp(last_record).date()
    unix_start = int(time.mktime(last_record.timetuple()))
    distinct_loc_type = access_database_with_result('traffic.db', \
        f"SELECT DISTINCT location, type FROM traffic WHERE time >= '{unix_start}' AND mode = 1")
    vehicle = {0: 'car', 1: 'van', 2: 'truck', 3: 'taxi', 4: 'other', 5: 'motorbike', 6: 'bicycle', 7: 'bus'}
    lst = []
    for loc, v_type in distinct_loc_type:
        occ_1 = access_database_with_result('traffic.db', f"SELECT * FROM traffic WHERE occupancy = 1 AND location = '{loc}' AND type = '{v_type}' AND mode = 1")
        occ_2 = access_database_with_result('traffic.db', f"SELECT * FROM traffic WHERE occupancy = 2 AND location = '{loc}' AND type = '{v_type}' AND mode = 1")
        occ_3 = access_database_with_result('traffic.db', f"SELECT * FROM traffic WHERE occupancy = 3 AND location = '{loc}' AND type = '{v_type}' AND mode = 1")
        occ_4 = access_database_with_result('traffic.db', f"SELECT * FROM traffic WHERE occupancy = 4 AND location = '{loc}' AND type = '{v_type}' AND mode = 1")
        if len(occ_1) != 0 or len(occ_2) != 0 or len(occ_3) != 0 or len(occ_4) != 0:
            lst.append(f'"{loc}",{vehicle[v_type]},{len(occ_1)},{len(occ_2)},{len(occ_3)},{len(occ_4)}')
    return lst

def db_csv_hours():
    last_record = access_database_with_result('traffic.db', 'SELECT MAX(end) FROM session WHERE end != 0')[0][0]
    day = datetime.fromtimestamp(last_record).date()
    week = datetime.fromtimestamp(last_record).date() - timedelta(days = 6)
    month = datetime.fromtimestamp(last_record).date() - relativedelta(months = 1) + timedelta(days = 1)
    unix_day = int(time.mktime(day.timetuple()))
    unix_week = int(time.mktime(week.timetuple()))
    unix_month = int(time.mktime(month.timetuple()))
    hours_day = []
    hours_week = []
    hours_month = []
    for i in range(1, len(access_database_with_result('traffic.db', "SELECT * FROM users")) + 1):
        hours_day.append(access_database_with_result('traffic.db', f"SELECT SUM(end - start) FROM session \
                                                    WHERE end != 0 AND start >= '{unix_day}' \
                                                    AND userid = {i}")[0][0])
    for i in range(1, len(access_database_with_result('traffic.db', "SELECT * FROM users")) + 1):
        hours_week.append(access_database_with_result('traffic.db', f"SELECT SUM(end - start) FROM session \
                                                    WHERE end != 0 AND start >= '{unix_week}' \
                                                    AND userid = {i}")[0][0])
    for i in range(1, len(access_database_with_result('traffic.db', "SELECT * FROM users")) + 1):
        hours_month.append(access_database_with_result('traffic.db', f"SELECT SUM(end - start) FROM session \
                                                    WHERE end != 0 AND start >= '{unix_month}' \
                                                    AND userid = {i}")[0][0])
    hours_day = [0 if element is None else math.ceil(element/360)/10 for element in hours_day]
    hours_week = [0 if element is None else math.ceil(element/360)/10 for element in hours_week]
    hours_month = [0 if element is None else math.ceil(element/360)/10 for element in hours_month]

    return hours_day, hours_week, hours_month

# HTTPRequestHandler class
class myHTTPServer_RequestHandler(BaseHTTPRequestHandler):

    # GET This function responds to GET requests to the web server.
    def do_GET(self):

        # The set_cookies function adds/updates two cookies returned with a webpage.
        # These identify the user who is logged in. The first parameter identifies the user
        # and the second should be used to verify the login session.
        def set_cookies(x, user, magic):
            ucookie = Cookie.SimpleCookie()
            ucookie['u_cookie'] = user
            x.send_header("Set-Cookie", ucookie.output(header='', sep=''))
            mcookie = Cookie.SimpleCookie()
            mcookie['m_cookie'] = magic
            x.send_header("Set-Cookie", mcookie.output(header='', sep=''))

        # The get_cookies function returns the values of the user and magic cookies if they exist
        # it returns empty strings if they do not.
        def get_cookies(source):
            rcookies = Cookie.SimpleCookie(source.headers.get('Cookie'))
            user = ''
            magic = ''
            for keyc, valuec in rcookies.items():
                if keyc == 'u_cookie':
                    user = valuec.value
                if keyc == 'm_cookie':
                    magic = valuec.value
            return [user, magic]

        # Fetch the cookies that arrived with the GET request
        # The identify the user session.
        user_magic = get_cookies(self)

        print(user_magic)

        # Parse the GET request to identify the file requested and the parameters
        parsed_path = urllib.parse.urlparse(self.path)

        # Decided what to do based on the file requested.

        # Return a CSS (Cascading Style Sheet) file.
        # These tell the web client how the page should appear.
        if self.path.startswith('/css'):
            self.send_response(200)
            self.send_header('Content-type', 'text/css')
            self.end_headers()
            with open('.'+self.path, 'rb') as file:
                self.wfile.write(file.read())
            file.close()

        # Return a Javascript file.
        # These tell contain code that the web client can execute.
        elif self.path.startswith('/js'):
            self.send_response(200)
            self.send_header('Content-type', 'text/js')
            self.end_headers()
            with open('.'+self.path, 'rb') as file:
                self.wfile.write(file.read())
            file.close()

        # A special case of '/' means return the index.html (homepage)
        # of a website
        elif parsed_path.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('./index.html', 'rb') as file:
                self.wfile.write(file.read())
            file.close()

        # Return html pages.
        elif parsed_path.path.endswith('.html'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('.'+parsed_path.path, 'rb') as file:
                self.wfile.write(file.read())
            file.close()

        # The special file 'action' is not a real file, it indicates an action
        # we wish the server to execute.
        elif parsed_path.path == '/action':
            self.send_response(200) #respond that this is a valid page request
            # extract the parameters from the GET request.
            # These are passed to the handlers.
            parameters = urllib.parse.parse_qs(parsed_path.query)

            if 'command' in parameters:
                # check if one of the parameters was 'command'
                # If it is, identify which command and call the appropriate handler function.
                if parameters['command'][0] == 'login':
                    [user, magic, response] = handle_login_request(user_magic[0], user_magic[1], parameters)
                    #The result of a login attempt will be to set the cookies to identify the session.
                    set_cookies(self, user, magic)
                elif parameters['command'][0] == 'add':
                    [user, magic, response] = handle_add_request(user_magic[0], user_magic[1], parameters)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif parameters['command'][0] == 'undo':
                    [user, magic, response] = handle_undo_request(user_magic[0], user_magic[1], parameters)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif parameters['command'][0] == 'back':
                    [user, magic, response] = handle_back_request(user_magic[0], user_magic[1], parameters)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif parameters['command'][0] == 'summary':
                    [user, magic, response] = handle_summary_request(user_magic[0], user_magic[1], parameters)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif parameters['command'][0] == 'logout':
                    [user, magic, response] = handle_logout_request(user_magic[0], user_magic[1], parameters)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                else:
                    # The command was not recognised, report that to the user.
                    response = []
                    response.append(build_response_refill('message', 'Internal Error: Command not recognised.'))

            else:
                # There was no command present, report that to the user.
                response = []
                response.append(build_response_refill('message', 'Internal Error: Command not found.'))

            text = json.dumps(response)
            print(text)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(bytes(text, 'utf-8'))

        elif self.path.endswith('/statistics/hours.csv'):
            ## if we get here, the user is looking for a statistics file
            ## this is where requests for /statistics/hours.csv should be handled.
            ## you should check a valid user is logged in. You are encouraged to wrap this behavour in a function.
            text = "Username,Day,Week,Month\n"
            for i in range(0,10):
                text += f"test{i+1},{db_csv_hours()[0][i]},{db_csv_hours()[1][i]},{db_csv_hours()[2][i]}\n"
            encoded = bytes(text, 'utf-8')
            self.send_response(200)
            self.send_header('Content-type', 'text/csv')
            self.send_header("Content-Disposition", 'attachment; filename="{}"'.format('hours.csv'))
            self.send_header("Content-Length", len(encoded))
            self.end_headers()
            self.wfile.write(encoded)

        elif self.path.endswith('/statistics/traffic.csv'):
            ## if we get here, the user is looking for a statistics file
            ## this is where requests for  /statistics/traffic.csv should be handled.
            ## you should check a valid user is checked in. You are encouraged to wrap this behavour in a function.
            text = "Location,Type,Occupancy1,Occupancy2,Occupancy3,Occupancy4\n"
            for element in db_csv_traffic():
                text += str(element) + "\n"
            encoded = bytes(text, 'utf-8')
            self.send_response(200)
            self.send_header('Content-type', 'text/csv')
            self.send_header("Content-Disposition", 'attachment; filename="{}"'.format('traffic.csv'))
            self.send_header("Content-Length", len(encoded))
            self.end_headers()
            self.wfile.write(encoded)

        else:
            # A file that does n't fit one of the patterns above was requested.
            self.send_response(404)
            self.end_headers()
        return

def run():
    """This is the entry point function to this code."""
    print('starting server...')
    ## You can add any extra start up code here
    # Server settings
    # Choose port 8081 over port 80, which is normally used for a http server
    if len(sys.argv) < 2: # Check we were given both the script name and a port number
        print("Port argument not provided.")
        return
    server_address = ('127.0.0.1', int(sys.argv[1]))
    httpd = HTTPServer(server_address, myHTTPServer_RequestHandler)
    print('running server on port =',sys.argv[1],'...')
    httpd.serve_forever() # This function will not return till the server is aborted.

run()
