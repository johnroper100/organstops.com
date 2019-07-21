import os
from html.parser import HTMLParser


class MyHTMLParser(HTMLParser):
    def handle_starttag(self, tag, attrs):
        print("Encountered a start tag:", tag)
        print(attrs)

    def handle_endtag(self, tag):
        print("Encountered an end tag :", tag)

    def handle_data(self, data):
        print("Encountered some data  :", data)


parser = MyHTMLParser()

for subdir, dirs, files in os.walk("."):
    for file in files:
        print(os.path.join(subdir, file))
        cur = open(os.path.join(subdir, file), 'r')
        parser.feed(cur.read())
