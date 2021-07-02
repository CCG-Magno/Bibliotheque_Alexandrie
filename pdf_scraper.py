#!/usr/bin/env python3.6

import  csv, datetime, json, re, typing
from typing import Sequence, Generator, Any

import tweepy, PyPDF2


class PDF_To_Tweet:
    '''
        Internal class for scraping PDF's (with notable exceptions) using Regular Expression matching and enforcing Tweet constraints.
    '''
    def __init__(self, file_to_process='')->None:
        self.pattern = re.compile(r'(?P<word>(\s|\w)+)(\s|\w)*(?P<terminator>([\,]|[\.]|[\;]|[\:]))?\s*')
        assert(type(file_to_process)==str)
        self.pdf_file = file_to_process

        return

    def _verify_valid_page_ranges(self, start, end, num_total_pages)->bool:
        return (start < num_total_pages  and start >= 0 ) and ((end >= start) and (end < num_total_pages) )
            

    def process_pdf_page_by_page(self, start=0, end=0):
        '''
            Generates PDF pages with range [start, end) assuming that the current PDF_To_Tweet object has a valid file provided.
        '''
        try:
            with  open(self.pdf_file, 'rb') as pdf:
                pdf_reader = PyPDF2.PdfFileReader(pdf)

                assert(self._verify_valid_page_ranges(start, end, pdf_reader.numPages) == True)
                
                for page_num in range(start, end):
                    yield page_num, pdf_reader.getPage(page_num)
            
        except FileNotFoundError as e:
            print(f"[!] Exception [{e}] \n\t\t raised while opening: {self.pdf_file}\n\n")

    def parse_texts_to_tweet_format(self, text)->Sequence[str]:
        
        matches = re.findall(self.pattern, text)

        parsed_tweets = []
        curr_text = ''
        for group in matches:   
            if group is None:
                continue

            prev = None
            for indiv in group:
                # Avoid including duplicates falsely detected by broken RegEx
                if indiv == '' or indiv == prev :
                    continue
                else:
                    if len(curr_text) + len(indiv) <= Tweet._char_limit:
                        curr_text += indiv
                    else:
                        parsed_tweets.append(curr_text)
                        curr_text = ''# put '@'+username+' ' here to ensure proper thread structure
                        if len(curr_text) + len(indiv) <= Tweet._char_limit:
                            curr_text += indiv #TODO:  this breaks a lof of behaviour need a better way to break up text and not lose chars!
                prev = indiv

        if curr_text not in parsed_tweets:
            parsed_tweets.append(curr_text)

        return parsed_tweets


class Tweet:
    '''
        Internal class representing Tweets for ease of processing and character limit enforcement.
    '''
    _char_limit = 280

    def __init__(self, username="", text="", is_part_of_thread=False):
        assert(Tweet._char_limit == 280)
        self.username = username
        self.text = text
        assert( self._valid_tweet_length() == True )
        self.date = datetime.datetime.now()
        self.id = None
        self.is_part_of_thread = is_part_of_thread
        return
    
    def _valid_tweet_length(self)->bool:
        return (len(self.text) <= Tweet._char_limit) and (len(self.text) >= 0)

def setup_twitter_api()->tweepy.API:

    access_token, access_token_secret, consumer_key, consumer_secret = get_auth_keys()
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    api = tweepy.API(auth)
    return api

def get_auth_keys()->(str, str, str, str):
    '''
        Retrieves authentication developers.twitter.com keys from a secrets.csv file locally stored in the project directory.
        The file is missing from the published repo to avoid security risks and exposing my testing accounts used.

        The expected order for the tokens in the secrets.csv file are:
        Access API Token, Access Secret Token, Consumer Key and Consumer Secret.\n
    '''
    access_token, access_token_secret, consumer_key, consumer_secret = None, None, None, None
    try:
        with open('secrets.csv') as secrets_file:
            reader = csv.reader(secrets_file, delimiter=',')
            for row in reader:
                consumer_key, consumer_secret, access_token, access_token_secret = str(row[0]).strip(), str(row[1]).strip(), str(row[2]).strip(), str(row[3]).strip()
                break

    except Exception as e:
        print(f"[!] Exception [{e}] \n\t\t raised while opening: secrets")

    return fr"{access_token}", fr"{access_token_secret}", fr"{consumer_key}", fr"{consumer_secret}"


def create_paginated_texts_as_tweet_thread(start, end, pdf_converter):
    '''
        Generates a Tweet-esque Thread from a provided PDF_To_Tweet object that complies with the Tweet class _char_limit=280
    '''
    for num, page in pdf_converter.process_pdf_page_by_page(start=start, end=end):
        for text in pdf_converter.parse_texts_to_tweet_format(page.extractText()):

            yield Tweet(text=text)
            

def  post_thread_tweets(start_page=12, end_page=13, pdf_to_open='don_quijote_esp.pdf')->Sequence[Tweet]:
    '''
    Posts the Thread of Tweets scraped from @arg start_page to @arg end_page of @arg pdf_to_open with the authenticated account.
    '''
    api = setup_twitter_api()

    pdf_converter = PDF_To_Tweet(file_to_process=pdf_to_open)
    tweets = [tweet for tweet in create_paginated_texts_as_tweet_thread(
                                                                        start=start_page,
                                                                        end=end_page,
                                                                        pdf_converter=pdf_converter)]
    prev_id = -1
    for idx, new_tweet in enumerate(tweets):
    
        # The status object returned contains already the ID of the posted tweet if it is successful!
        # we can use this to create the threads one after another!
        if idx == 0:
            # first tweet post!
            # tweet here to our profile
            tweet_result = api.update_status(status=new_tweet.text)._json
            # we need to retrieve ID for first time
            new_tweet.id = tweet_result['id']
            prev_id = tweet_result['id']
        else:
            if prev_id != -1:
                tweet_result = api.update_status(status=new_tweet.text,
                                                 in_reply_to_status_id=prev_id,
                                                 in_reply_to_status_id_str=str(prev_id))._json
                new_tweet.id = tweet_result['id']
                prev_id =  tweet_result['id']

    
    return tweets


def post_tweet(pdf_to_open='don_quijote_esp.pdf')-> None:
    '''
    Posts a single Tweet scraped from @arg start_page to @arg end_page of @arg pdf_to_open with the authenticated account.
    '''
    api = setup_twitter_api()

    pdf_file = open(pdf_to_open, 'rb')
    pdf_reader = PyPDF2.PdfFileReader(pdf_file)

    # number pages
    print(f"PDF Total Pages [{pdf_reader.numPages}]\n")

    page = pdf_reader.getPage(57)
    new_tweet = Tweet(page.extractText())
    
    pdf_file.close()

    # tweet here to our profile
    print(api.update_status(status=new_tweet.text))
    # The status object returned contains already the ID of the posted tweet if it is successful!
    # we can use this to create the threads one after another!
    return

post_thread_tweets()
