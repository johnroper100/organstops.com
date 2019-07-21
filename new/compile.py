from jinja2 import Template
import os
import json
import shutil

def getLetter(name):
    return name[0].lower()

def getNameURL(name):
    return name.replace(" ", "_")

stopTemplateFile = open(os.path.join("templates", "stop.html"), 'r')
stopTemplate = Template(stopTemplateFile.read())
stopTemplateFile.close()

indexTemplateFile = open(os.path.join("templates", "index.html"), 'r')
indexTemplate = Template(indexTemplateFile.read())
indexTemplateFile.close()

if os.path.exists("build"):
    shutil.rmtree("build")

os.makedirs("build")
shutil.copytree("images", os.path.join("build", "images"))
shutil.copytree("audio", os.path.join("build", "audio"))

names = []

for subdir, dirs, files in os.walk("definitions"):
    for file in files:
        with open(os.path.join(subdir, file)) as definition:
            data = json.load(definition)
            names.extend(data['names'])
            name = next(item for item in data['names'] if item['primary'] == True)[
                'name']
            
            nameURL = getNameURL(name)
            letter = getLetter(name)
            if not os.path.exists(os.path.join("build",letter)):
                os.makedirs(os.path.join("build",letter))
            f = open(os.path.join("build",letter, nameURL+".html"), "w")
            f.write(stopTemplate.render(data, name=name, letter=letter, nameURL=nameURL, getNameURL=getNameURL, getLetter=getLetter))
            f.close()