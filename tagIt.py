#!/usr/bin/env python
import sys, os, json, time, random, math, urllib, urllib2, pycurl, subprocess, boto, boto3, boto.s3, os.path, requests, StringIO, os.path, argparse, signal
import RPi.GPIO as GPIO
from subprocess import call
##SETUP FOR AWS CONNECTION
# Fill these in - you get them when you sign up for S3
AWS_ACCESS_KEY_ID = 'YOUR ACCESS KEY ID'
AWS_ACCESS_KEY_SECRET = 'YOUR SECRET PASSWORD'
# Fill in info on data to upload destination bucket name
bucket_name = 'tagit-imagebucket'
# source directory
sourceDir = '/home/pi/tagit/image/'
# destination directory name (on s3)
destDir = ''
filename='testimage.jpg'
#max size in bytes before uploading in parts. between 1 and 5 GB
#recommended
MAX_SIZE = 20 * 1000 * 1000
#size of parts when uploading in parts
PART_SIZE = 6 * 1000 * 1000
conn = boto.connect_s3(AWS_ACCESS_KEY_ID, AWS_ACCESS_KEY_SECRET)
bucket = conn.get_bucket(bucket_name)
#bucket = conn.create_bucket(bucket_name,
#       location=boto.s3.connection.Location.DEFAULT)
##SETUP FOR TRANSLATION
LANGUAGE = "en-US" # Language to use with TTS - this won't do any translation, just the voice it's spoken with
ENCODING = "UTF-8" # Character encoding to use
text="An error occurred while analyzing the photo. Please retry"
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN)
translation= ""

def percent_cb(complete, total):
    sys.stdout.write('.')
    sys.stdout.flush()

def kill_mpg123():

        p = subprocess.Popen(['ps', '-A'], stdout=subprocess.PIPE)
        out, err = p.communicate()
        for line in out.splitlines():
                if 'mpg123' in line:
                        pid = int(line.split(None, 1)[0])
                        os.kill(pid, signal.SIGKILL)

def upload ():
        global sourceDir
        uploadFileNames = []
        for (sourceDir, dirname, filename) in os.walk(sourceDir):
                uploadFileNames.extend(filename)
                break
        for filename in uploadFileNames:
                sourcepath = os.path.join(sourceDir + filename)
                destpath = os.path.join(destDir, filename)
                print 'Uploading %s to Amazon S3 bucket %s' % \
                        (sourcepath, bucket_name)
                filesize = os.path.getsize(sourcepath)
                if filesize > MAX_SIZE:
                        print "multipart upload"
                        mp = bucket.initiate_multipart_upload(destpath)
                        fp = open(sourcepath,'rb')
                        fp_num = 0
                        while (fp.tell() < filesize):
                                fp_num += 1
                                print "uploading part %i" %fp_num
                                mp.upload_part_from_file(fp, fp_num, cb=percent_cb, num_cb=10, size=PART_SIZE)
                        mp.complete_upload()

                else:
                        print "singlepart upload"
                        k = boto.s3.key.Key(bucket)
                        k.key = destpath
                        k.set_contents_from_filename(sourcepath,cb=percent_cb, num_cb=10)

def rekognition (max_labels,min_confidence):
        rekognition = boto3.client("rekognition", "us-west-2")
        response = rekognition.detect_labels(
                Image={
                        "S3Object": {
                                "Bucket": bucket_name,
                                "Name": filename,
                        }
                },
                MaxLabels=max_labels,
                MinConfidence=min_confidence,
        )
        return response['Labels']

class Translator(object):
    oauth_url = 'https://datamarket.accesscontrol.windows.net/v2/OAuth2-13'
    translation_url ='http://api.microsofttranslator.com/V2/Ajax.svc/Translate?'

    def __init__(self):
        oauth_args = {
            'client_id': 'TranslatorPI',
            'client_secret': '[Microsoft Client Secret]',
            'scope': 'http://api.microsofttranslator.com',
            'grant_type': 'client_credentials'
        }
        oauth_junk = json.loads(requests.post(Translator.oauth_url, data=urllib.urlencode(oauth_args)).content)
        self.headers = {'Authorization': 'Bearer ' + oauth_junk['access_token']}

    def translate(self, origin_language, destination_language, text):

        translation_args = {
            'text': text,
            'to': destination_language,
            'from': origin_language
        }
        translation_result = requests.get(Translator.translation_url + urllib.urlencode(translation_args),
                                          headers=self.headers)
        translation = translation_result.text[2:-1]

        print "Translation: ", translation
        speak_text(origin_language, 'Translating ' + text)
        speak_text(destination_language, translation)

		
while True:
 text="An error occurred while analyzing the photo. Please retry"
 if GPIO.input(17):
        os.system("raspistill -t 1000 -hf -vf -o image/testimage.jpg")
        #Code for image uploading, Amazon WS Rekogniion Software and descricption retrieving
        upload()
        for label in rekognition(3, 70):
                text = "{Name} - {Confidence}%".format(**label)
                print text
                trunc = text.split("-")[0]
                call(["mpg123", "-q", "-y", "http://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&q=%s&tl=%s" % (trunc, LANGUAGE)])
                kill_mpg123()
