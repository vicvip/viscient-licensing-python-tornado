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

define("port", default=8888, help="run on the given port", type=int)

class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        return self.get_secure_cookie("user")
        
    def get_account_type(self):
        return self.get_secure_cookie("account_type")

    @staticmethod
    def get_back_end_url(self):
        return 'http://localhost:5000'

class MainHandler(BaseHandler):
    @tornado.web.authenticated
    @tornado.gen.coroutine
    def get(self):
        #print(self.remove_encode_format(self.get_account_type()))
        
        client = AsyncHTTPClient()
        username = to_unicode(self.current_user)
        account_type = to_unicode(self.get_account_type())

        license_details = None
        history_details = None
        user_counter = None
        user_details = None
        #client = httpclient.HTTPClient()
        try:
            query_license_response = yield client.fetch(
                'http://localhost:5000/licensing/query_licensing?username=test')
            deserealized_query_license_body = json.loads(query_license_response.body)
            responseCode = deserealized_query_license_body['statusCode']
            #if(responseCode is not 200):
                #handle this somehow...?
            
            license_details = deserealized_query_license_body['license']
            #print(deserealized_query_license_body['statusCode'])
        except Exception as e:
            print(f'Server error with query_license: {e}')
        
        try:
            history_details_response = yield client.fetch(
                f'http://localhost:5000/mongodbservice/history?username={username}&accountType={account_type}')
            deserealized_history_details_body = json.loads(history_details_response.body)
            responseCode = deserealized_history_details_body['statusCode']
            #print(history_details_response.body)
            #if(responseCode is not 200):
                #handle this somehow...?
            
            history_details = deserealized_history_details_body['historyDetails']
            #print(history_details)
        except Exception as e:
            print(f'Server error with history: {e}')

        try:
            user_counter_response = yield client.fetch(
                f'http://localhost:5000/mongodbservice/user_counter?username={username}')
            deserealized_user_counter_body = json.loads(user_counter_response.body)
            responseCode = deserealized_user_counter_body['statusCode']
            #if(responseCode is not 200):
                #handle this somehow...?
            
            user_counter = deserealized_user_counter_body['poc_counter']
        except Exception as e:
            print(f'Server error with history: {e}')

        if(account_type == 'admin'):
            try:
                user_details_response = yield client.fetch('http://localhost:5000/mongodbservice/all_user')
                deserealized_user_details_body = json.loads(user_details_response.body)
                responseCode = deserealized_user_details_body['statusCode']
                #if(responseCode is not 200):
                    #handle this somehow...?
                
                user_details = deserealized_user_details_body['userDetails']
            except:
                 print(f'Server error with user details: {e}')

        self.render('index.html', license_details=license_details, history_details=history_details, user_counter=user_counter, user_details=user_details, account_type=account_type)

class LoginHandler(BaseHandler):
    @tornado.gen.coroutine
    def get(self):
        incorrect = self.get_secure_cookie("incorrect")
        if incorrect and int(incorrect) > 20:
            self.write('<center>blocked</center>')
            return
        self.render('login.html')

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
            'http://localhost:5000/mongodbservice/login', method='POST', body=body,
            headers={'Content-Type': 'application/json'}
            )
            deserealized_login_body = json.loads(login_response.body)
            responseCode = deserealized_login_body['statusCode']
            #print(responseCode)
        except Exception as e:
            print(f'Server error: {e}')

        if(responseCode is 200):
            account_type = deserealized_login_body['accountType']

            self.set_secure_cookie("user", self.get_argument("username"))
            self.set_secure_cookie("account_type", account_type)
            self.set_secure_cookie("incorrect", "0")
            self.redirect(self.reverse_url("main"))
        else:
            incorrect = self.get_secure_cookie("incorrect") or 0
            increased = str(int(incorrect)+1)
            self.clear_cookie("user")
            self.set_secure_cookie("incorrect", increased)
            self.write("""<center>
                            Something Wrong With Your Data (%s)<br />
                            <a href="/">Go Home</a>
                          </center>""" % increased)

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
            'http://localhost:5000/licensing/activation', method='POST', body=body,
            headers={'Content-Type': 'application/json'}
            )
            #deserealized_activation_body = json.loads(activation_response.body)
            #responseCode = deserealized_activation_body['statusCode']
            #print(responseCode)
        except Exception as e:
            print(f'Server error with activation: {e}')

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
            'http://localhost:5000/licensing/extension', method='POST', body=body,
            headers={'Content-Type': 'application/json'}
            )
            deserealized_extension_body = json.loads(extension_response.body)
            #responseCode = deserealized_activation_body['statusCode']
            print(deserealized_extension_body)
        except Exception as e:
            print(f'Server error with extension: {e}')
            
        #print(self)
        self.redirect(self.reverse_url("main"))

class AddCreditHandler(BaseHandler):
    @tornado.gen.coroutine
    def post(self):
        client = AsyncHTTPClient()

        increment_value = tornado.escape.xhtml_escape(self.get_argument("increment_value")) 
        target_username = tornado.escape.xhtml_escape(self.get_argument("target_username"))

        print(target_username)
        body = json.dumps({
            "username": target_username,
            "increment_value": int(increment_value)
        })

        try:
            extension_response = yield client.fetch(
            'http://localhost:5000/mongodbservice/increment_user_credit', method='POST', body=body,
            headers={'Content-Type': 'application/json'}
            )
            deserealized_extension_body = json.loads(extension_response.body)
            #responseCode = deserealized_activation_body['statusCode']
            print(deserealized_extension_body)
        except Exception as e:
            print(f'Server error with extension: {e}')

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