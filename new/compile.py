import copy
import json
import os
import shutil

from jinja2 import Template


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

missingTemplateFile = open(os.path.join("templates", "missing.html"), 'r')
missingTemplate = Template(missingTemplateFile.read())
missingTemplateFile.close()

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
            name = next(item for item in data['names'] if item['primary'] == True)[
                'name']

            for nameItem in data['names']:
                newName = copy.deepcopy(nameItem)
                del newName['primary']
                del newName['origin']
                if newName['link'] != "":
                    if newName not in names:
                        names.append(newName)
                        newNewName = copy.deepcopy(newName)
                        newNewName['name'] = newNewName['name'] + " ("+name+")"
                        newNewName['link'] = name
                        if newNewName not in names:
                            names.append(newNewName)
                else:
                    newName['link'] = name
                    if newName not in names:
                        names.append(newName)

            for nameItem in data['variants']:
                newName = copy.deepcopy(nameItem)
                if newName['link'] != "":
                    if newName['link'] != newName['name']:
                        newNewName = copy.deepcopy(newName)
                        newNewName['name'] = newNewName['name'] + \
                            " ("+newNewName['link']+")"
                        if newNewName not in names:
                            names.append(newNewName)
                    else:
                        if newName not in names:
                            names.append(newName)

            for nameItem in data['comparisons']:
                newName = copy.deepcopy(nameItem)
                if newName['link'] != "":
                    if newName['link'] != newName['name']:
                        newNewName = copy.deepcopy(newName)
                        newNewName['name'] = newNewName['name'] + \
                            " ("+newNewName['link']+")"
                        if newNewName not in names:
                            names.append(newNewName)
                    else:
                        if newName not in names:
                            names.append(newName)

            nameURL = getNameURL(name)
            letter = getLetter(name)
            if not os.path.exists(os.path.join("build", letter)):
                os.makedirs(os.path.join("build", letter))
            f = open(os.path.join("build", letter, nameURL+".html"), "w")
            f.write(stopTemplate.render(data, name=name, letter=letter,
                                        nameURL=nameURL, getNameURL=getNameURL, getLetter=getLetter))
            f.close()

names = sorted(names, key=lambda k: k['name'])

for name in names:
    if not os.path.exists(os.path.join("definitions", getLetter(name['link']), getNameURL(name['link'])+".json")):
        if not os.path.exists(os.path.join("build", getLetter(name['link']))):
            os.makedirs(os.path.join("build", getLetter(name['link'])))
        f = open(os.path.join("build", getLetter(
            name['link']), getNameURL(name['link'])+".html"), "w")
        f.write(missingTemplate.render(
            name=name, getNameURL=getNameURL, getLetter=getLetter))
        f.close()
        name['exists'] = False
    else:
        name['exists'] = True

f = open(os.path.join("build", "index.html"), "w")
f.write(indexTemplate.render(names=names,
                             getNameURL=getNameURL, getLetter=getLetter))
f.close()


