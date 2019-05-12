#!/usr/bin/env python
#-*- coding:utf-8 -*-

import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.options
import tornado.gen
from tornado.escape import to_unicode
import os.path
import json
from tornado.httpclient import AsyncHTTPClient
from tornado.options import define, options

from datetime import datetime
import pytz    
import tzlocal 

define("port", default=8888, help="run on the given port", type=int)

class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        return self.get_secure_cookie("user")
        
    def get_account_type(self):
        return self.get_secure_cookie("account_type")

    @staticmethod
    def get_back_end_url():
        # return 'http://localhost:5000'
        return 'https://viscient-licensing-py-flask.herokuapp.com'
    
    @staticmethod
    def set_headers():
        return json.dumps({
            'X-API-KEY': 'OdRGF2aAqH323q0WlX5JOfRtaCVpQbbN',
            'Content-Type': 'application/json'}
        )

    @staticmethod
    def convert_date_to_local(date):
        local_timezone = tzlocal.get_localzone()
        utc_time = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%f")
        local_time = utc_time.replace(tzinfo=pytz.utc).astimezone(local_timezone).strftime('%Y-%m-%dT%H:%M:%S')
        return local_time

class MainHandler(BaseHandler):
    @tornado.web.authenticated
    @tornado.gen.coroutine
    def get(self):
        client = AsyncHTTPClient()
        username = to_unicode(self.current_user)
        account_type = to_unicode(self.get_account_type())

        license_details = None
        history_details = None
        user_counter = None
        user_details = None
        try:
            query_license_response = yield client.fetch(
                f'{self.get_back_end_url()}/licensing/query_licensing?username=test', headers=json.loads(self.set_headers())
            )
            deserealized_query_license_body = json.loads(query_license_response.body)
            license_details = deserealized_query_license_body['license']
        except Exception as e:
            print('Server error with query_license: ')
            print(e)
            self.render('login.html', credential_validated=True, server_error=True)
        
        try:
            history_details_response = yield client.fetch(
                f'{self.get_back_end_url()}/mongodbservice/history?username={username}&accountType={account_type}', headers=json.loads(self.set_headers())
            )
            deserealized_history_details_body = json.loads(history_details_response.body)
            history_details = deserealized_history_details_body['history_details']

            for history in history_details:
                history['dateCreated'] = self.convert_date_to_local(history['dateCreated'])
                history['dateExpired'] = self.convert_date_to_local(history['dateExpired'])
        except Exception as e:
            print('Server error with history: ')
            print(e)
            self.render('login.html', credential_validated=True, server_error=True)

        try:
            user_counter_response = yield client.fetch(
                f'{self.get_back_end_url()}/mongodbservice/user_counter?username={username}', headers=json.loads(self.set_headers())
            )
            deserealized_user_counter_body = json.loads(user_counter_response.body)
            user_counter = deserealized_user_counter_body['poc_counter']
        except Exception as e:
            print('Server error with user counter: ')
            print(e)
            self.render('login.html', credential_validated=True, server_error=True)

        if(account_type == 'admin'):
            try:
                user_details_response = yield client.fetch(
                    f'{self.get_back_end_url()}/mongodbservice/all_user', headers=json.loads(self.set_headers())
                )
                deserealized_user_details_body = json.loads(user_details_response.body)
                user_details = deserealized_user_details_body['user_details']
            except:
                print('Server error with all users: ')
                print(e)
                self.render('login.html', credential_validated=True, server_error=True)

        self.render('index.html', license_details=license_details, history_details=history_details, user_counter=user_counter, user_details=user_details, account_type=account_type)

class LoginHandler(BaseHandler):
    @tornado.gen.coroutine
    def get(self):
        incorrect = self.get_secure_cookie("incorrect")
        if incorrect and int(incorrect) > 20:
            self.write('<center>blocked</center>')
            return
        self.render('login.html', credential_validated=True, server_error=False)

    @tornado.gen.coroutine
    def post(self):
        incorrect = self.get_secure_cookie("incorrect")
        if incorrect and int(incorrect) > 20:
            self.write('<center>blocked</center>')
            return
        
        getusername = tornado.escape.xhtml_escape(self.get_argument("username"))
        getpassword = tornado.escape.xhtml_escape(self.get_argument("password"))
        
        client = AsyncHTTPClient()
        body = json.dumps({
            'username': getusername,
            'password': getpassword
        })

        deserealized_login_body = None
        responseCode = 404
        try:
            login_response = yield client.fetch(
                f'{self.get_back_end_url()}/mongodbservice/login', method='POST', body=body,
                headers=json.loads(self.set_headers())
            )
            deserealized_login_body = json.loads(login_response.body)
            responseCode = deserealized_login_body['status_code']
        except Exception as e:
            print(f'Server error: {e}')

        if(responseCode is 200):
            account_type = deserealized_login_body['accountType']

            self.set_secure_cookie("user", self.get_argument("username"))
            self.set_secure_cookie("account_type", account_type)
            self.set_secure_cookie("incorrect", "0")
            self.redirect(self.reverse_url("main"))
        else:
            self.clear_cookie("user")
            self.render('login.html', credential_validated=False, server_error=False)

class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("user")
        self.redirect(self.get_argument("next", self.reverse_url("main")))

class ActivationHandler(BaseHandler):
    @tornado.gen.coroutine
    def post(self):
        account_type = to_unicode(self.get_account_type())

        username = tornado.escape.xhtml_escape(self.get_argument("username")) if (account_type == 'admin') else to_unicode(self.current_user)
        domain_name = tornado.escape.xhtml_escape(self.get_argument("domain_name")) 
        number_of_days = tornado.escape.xhtml_escape(self.get_argument("number_of_days")) if (account_type == 'admin') else 10

        client = AsyncHTTPClient()
        body = json.dumps({
            "username": username,
            "domainName": domain_name,
            "numberOfDays": int(number_of_days),
            "accountType": account_type
        })

        try:
            activation_response = yield client.fetch(
                f'{self.get_back_end_url()}/licensing/activation', method='POST', body=body,
                headers=json.loads(self.set_headers())
            )
        except Exception as e:
            print('Server error with activation: ')
            print(e)
            self.render('login.html', credential_validated=True, server_error=True)

        self.redirect(self.reverse_url("main"))

class ExtensionHandler(BaseHandler):
    @tornado.gen.coroutine
    def post(self):
        account_type = to_unicode(self.get_account_type())

        username = tornado.escape.xhtml_escape(self.get_argument("username")) if (account_type == 'admin') else to_unicode(self.current_user)
        domain_name = tornado.escape.xhtml_escape(self.get_argument("domain_name")) 
        number_of_days = tornado.escape.xhtml_escape(self.get_argument("number_of_days")) if (account_type == 'admin') else 10

        client = AsyncHTTPClient()
        body = json.dumps({
            "username": username,
            "domainName": domain_name,
            "numberOfDays": int(number_of_days),
            "accountType": account_type
        })

        try:
            extension_response = yield client.fetch(
                f'{self.get_back_end_url()}/licensing/extension', method='POST', body=body,
                headers=json.loads(self.set_headers())
            )
        except Exception as e:
            print('Server error with extension: ')
            print(e)
            self.render('login.html', credential_validated=True, server_error=True)
            
        self.redirect(self.reverse_url("main"))

class AddCreditHandler(BaseHandler):
    @tornado.gen.coroutine
    def post(self):
        client = AsyncHTTPClient()

        increment_value = tornado.escape.xhtml_escape(self.get_argument("increment_value")) 
        target_username = tornado.escape.xhtml_escape(self.get_argument("target_username"))

        body = json.dumps({
            "username": target_username,
            "increment_value": int(increment_value)
        })

        try:
            extension_response = yield client.fetch(
                f'{self.get_back_end_url()}/mongodbservice/increment_user_credit', method='POST', body=body,
                headers=json.loads(self.set_headers())
            )
        except Exception as e:
            print('Server error with add credit: ')
            print(e)
            self.render('login.html', credential_validated=True, server_error=True)

        self.redirect(self.reverse_url("main"))


class Application(tornado.web.Application):
    def __init__(self):
        base_dir = os.path.dirname(__file__)
        settings = {
            "cookie_secret": "bZJc2sWbQLKos6GkHn/VB9oXwQt8S0R0kRvJ5/xJ89E=",
            "login_url": "/login",
            'template_path': os.path.join(base_dir, "templates"),
            'static_path': os.path.join(base_dir, "static"),
            'debug':True,
            "xsrf_cookies": True,
        }
        
        tornado.web.Application.__init__(self, [
            tornado.web.url(r"/", MainHandler, name="main"),
            tornado.web.url(r'/login', LoginHandler, name="login"),
            tornado.web.url(r'/logout', LogoutHandler, name="logout"),
            tornado.web.url(r'/activation', ActivationHandler, name="activation"),
            tornado.web.url(r'/extension', ExtensionHandler, name="extension"),
            tornado.web.url(r'/add_credit', AddCreditHandler, name="add_credit"),
        ], **settings)

def main():
    tornado.options.parse_command_line()
    Application().listen(options.port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()