from django.shortcuts import render,HttpResponse,redirect
from .forms import GForm,SimForm
from PIL import Image
import cv2
import numpy as np
import math
from django.http import HttpResponseRedirect,FileResponse
import time
from bs4 import BeautifulSoup
import os
import base64

# Create your views here.
def index(request):
    form = GForm(request.POST or None,request.FILES or None)
    if request.POST:
        if form.is_valid():
            request.session["form"] = form.as_p()
            img = Image.open(request.FILES["file"])
            img = np.array(img)
            try:
                img = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
            except:
                pass
            retval, buffer = cv2.imencode('.jpg', img)
            jpg_as_text = base64.b64encode(buffer)
            img = str(jpg_as_text)[2:]
            img = list(img)
            img.pop()
            img = "".join(img)
            request.session["img"] = img
            request.session["start"] = False
            return redirect("loading")
        else:
            print("not valid")
    return render(request,"index.html",{"form":form})

def gcode(request):
    code = "a"
    if 'code' in request.session:
        code = request.session["code"]
    context = {"code":code,"length":str(len(code.split("\n")))}
    return render(request,"gcode.html",context)

def loading(request):
    if 'start' in request.session:
        if request.session["start"] == True:
            if 'form' in request.session and 'img' in request.session:
                form = request.session["form"]
                img = request.session["img"]
                nparr = np.fromstring(base64.b64decode(img), np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                soup = BeautifulSoup(form, "html.parser")
                form = soup.find_all("input")
                height = float(form[1].get("value"))
                height = int(math.floor(height))
                width = float(form[2].get("value"))
                width = int(math.floor(width))
                precision = float(form[3].get("value"))
                digit = len(str(precision).split(".")[1])
                edge = float(form[4].get("value"))
                team = int(form[5].get("value"))
                s = int(form[6].get("value"))
                f = int(form[7].get("value"))
                zMax = float(form[8].get("value"))
                zMin = float(form[9].get("value"))
                checked = False
                if form[10].get("checked") != None:
                    checked = True
                gcode = ""
                med_val = np.median(img)
                
                low = int(max(0,(1 - 0.33)*med_val))
                high = int(min(255,(1 + 0.33)*med_val))

                edges = cv2.Canny(img,low,high)
                listOfCoords = []

                if checked:
                    edges = img
                    if len(edges.shape) > 2:
                        edges = cv2.cvtColor(edges,cv2.COLOR_BGR2GRAY)
                for idxY,y in enumerate(edges):
                    for idxX,x in enumerate(y):
                        if x > 250:
                            listOfCoords.append({"order":0,"x":idxX,"y":len(img)-idxY})

                #print(listOfCoords)

                orderV = 1
                curX = 0
                curY = 0
                listOfCoords[0]["order"] = 1
                x = 1

                #print("Pixel count: "+str(len(listOfCoords)))

                maxX = 0
                maxY = 0
                minX = 0
                minY = 0

                for coords in listOfCoords:
                    if coords["x"] < minX:
                        minX = coords["x"]

                    if coords["y"] < minY:
                        minY = coords["y"]

                for coords in listOfCoords:
                    coords["x"] += minX

                    coords["y"] += minY

                for coords in listOfCoords:
                    if coords["x"] > maxX:
                        maxX = coords["x"]

                    if coords["y"] > maxY:
                        maxY = coords["y"]

                xDivide = float(float(maxX)/float(width))
                yDivide = float(float(maxY)/float(height))

                lim = edge
                if precision > lim:
                    lim = precision
                lim = int(float(float(len(listOfCoords)/(width*height))*lim))
                if lim < 2:
                    lim = 2

                while True:
                    while True:
                        cur = list(filter(lambda coord: coord['order'] == orderV, listOfCoords))[0]
                        curX = cur["x"]
                        curY = cur["y"]
                        
                        giveOrder = True
                        for coords in listOfCoords:
                            if coords["order"] == 0 and giveOrder:
                                if (((abs(coords["y"] - curY) < lim)) and ((abs(coords["x"] - curX) < lim))) or (coords["y"] == curY and ((abs(coords["x"] - curX) < lim))) or (coords["x"] == curX and ((abs(coords["y"] - curY) < lim))):
                                    orderV += 1
                                    coords["order"] = orderV
                                    giveOrder = False
                        
                        if giveOrder:
                            break
                                

                    orderZeroList = list(filter(lambda coord: coord['order'] == 0, listOfCoords))
                    #print("Calculated "+str(len(listOfCoords)-len(orderZeroList))+" of "+str(len(listOfCoords))+" pixels")

                    if len(orderZeroList) > 0:
                        orderZeroChosen = orderZeroList[0]
                        dist = int(((abs(orderZeroList[0]["x"] - curX)**2) + (abs(orderZeroList[0]["y"] - curY)**2))**0.5)
                        for coords in orderZeroList:
                            if int(((abs(coords["x"]-curX)**2) + (abs(coords["y"]-curY)**2))**0.5) < dist:
                                orderZeroChosen = coords
                                dist = int(((abs(coords["x"]-curX)**2) + (abs(coords["y"]-curY)**2))**0.5)
                        
                        orderV += 2
                        for idx,coords in enumerate(listOfCoords):
                            if coords == orderZeroChosen:
                                listOfCoords[idx]["order"] = orderV

                    else:
                        #print("Done")
                        break

                for coords in listOfCoords:
                    coords["x"] = round(float(round(float(float(float(coords["x"])/xDivide)/precision))*precision),digit)
                    coords["y"] = round(float(round(float(float(float(coords["y"])/yDivide)/precision))*precision),digit)

                #print(listOfCoords)
                orderMax = 1
                for coords in listOfCoords:
                    if coords["order"] > orderMax:
                        orderMax = coords["order"]

                gcode = ""

                gcode += "G90 G21 G17 G80 G40 G54\nT"+str(team)+" M06\nS"+str(s)+". M03\nG00 X0. Y0. Z"+str(zMax/10)+"\n"
                onLine = 4
                #print("Written "+str(onLine)+" of "+str(lineCount)+" lines")
                orderV = 1
                started = False
                while True:
                    try:

                        if started:
                            gcode += "G01 X"+str(list(filter(lambda coord: coord['order'] == orderV, listOfCoords))[0]["x"])+" Y"+str(list(filter(lambda coord: coord['order'] == orderV, listOfCoords))[0]["y"])+"\n"
                            orderV += 1
                            onLine += 1
                            #print("Written "+str(onLine)+" of "+str(lineCount)+" lines")

                        else:
                            gcode += "G00 X"+str(list(filter(lambda coord: coord['order'] == orderV, listOfCoords))[0]["x"])+" Y"+str(list(filter(lambda coord: coord['order'] == orderV, listOfCoords))[0]["y"])+"\n"
                            gcode += "G01 Z"+str(zMin)+" F"+str(f)+"\n"
                            orderV += 1
                            started = True
                            onLine += 2
                            #print("Written "+str(onLine)+" of "+str(lineCount)+" lines")

                    except IndexError:
                        try:
                            orderV += 1
                            if (((float((list(filter(lambda coord: coord['order'] == orderV-2, listOfCoords))[0]["x"]) - float(list(filter(lambda coord: coord['order'] == orderV, listOfCoords))[0]["x"]))**2) + (float((list(filter(lambda coord: coord['order'] == orderV-2, listOfCoords))[0]["y"]) - float(list(filter(lambda coord: coord['order'] == orderV, listOfCoords))[0]["y"]))**2))**0.5) > edge:
                                gcode += "G01 Z"+str(zMax/10)+"\n"
                                gcode += "G00 X"+str(list(filter(lambda coord: coord['order'] == orderV, listOfCoords))[0]["x"])+" Y"+str(list(filter(lambda coord: coord['order'] == orderV, listOfCoords))[0]["y"])+"\n"
                                gcode += "G01 Z"+str(zMin)+"\n"

                            else:
                                gcode += "G01 X"+str(list(filter(lambda coord: coord['order'] == orderV, listOfCoords))[0]["x"])+" Y"+str(list(filter(lambda coord: coord['order'] == orderV, listOfCoords))[0]["y"])+"\n"
                            orderV += 1
                            onLine += 3
                            #print("Written "+str(onLine)+" of "+str(lineCount)+" lines")
                        except IndexError:
                            break

                gcode += "G01 Z"+str(zMax/10)+"\nG00 X0. Y0. Z"+str(zMax)+"\nM30"

                #print("Decreasing line count")
                while True:
                    for i in range(3):
                        idxPop = []
                        lines = gcode.split("\n")
                        for idx,line in enumerate(lines):
                            if idx != len(lines)-1:
                                lines[idx] += "\n"
                            if (line.startswith("G01") and "Z" not in line) and (lines[idx+1].startswith("G01") and "Z" not in lines[idx+1]):
                                coords1 = line
                                coords2 = lines[idx+1]

                                if coords1 == coords2:
                                    idxPop.append(idx+1)
                            

                        if idxPop != []:
                            idxPop.sort()
                            idxPop.reverse()
                            for i in idxPop:
                                lines.pop(i)
                            gcode = "".join(lines)
                            idxPop = []

                    lines = gcode.split("\n")
                    for idx,line in enumerate(lines):
                        if idx != len(lines)-1:
                            lines[idx] += "\n"
                        if (line.startswith("G01") and "Z" not in line) and (lines[idx+1].startswith("G01") and "Z" not in lines[idx+1]):
                            coords1 = line.split(" ")
                            coords2 = lines[idx+1].split(" ")

                            if coords1[1] == coords2[1]:
                                idxPop.append(idx+1)

                    if idxPop != []:
                        idxPop.sort()
                        idxPop.reverse()
                        for i in idxPop:
                            lines.pop(i)
                        gcode = "".join(lines)
                        idxPop = []

                    lines = gcode.split("\n")
                    for idx,line in enumerate(lines):
                        if idx != len(lines)-1:
                            lines[idx] += "\n"
                        if (line.startswith("G01") and "Z" not in line) and (lines[idx+1].startswith("G01") and "Z" not in lines[idx+1]):
                            coords1 = line.split(" ")
                            coords2 = lines[idx+1].split(" ")

                            if coords1[2] == coords2[2]:
                                idxPop.append(idx+1)

                    if idxPop != []:
                        idxPop.sort()
                        idxPop.reverse()
                        for i in idxPop:
                            lines.pop(i)
                        gcode = "".join(lines)
                    else:
                        break
                request.session["code"] = gcode
                request.session["start"] = False
                return redirect("gcode")
        else:
            request.session["start"] = True
    else:
        request.session["start"] = True
    return render(request,"loading.html")

def about(request):
    text = """Hi there! My name is Seymen, and I'm a high school student with a passion for software engineering. My expertise lies in Python programming, and I have advanced skills in using various libraries like Flask, Django, requests, pygame, pyqt5, opencv, pyserial, mediapipe, keras, and openai. I also have experience in Arduino programming and embedded systems design.

Apart from this, I am proficient in PCB design using Proteus and 3D design using SolidWorks. With Selenium, I can scrape data from websites and extract useful information using the BeautifulSoup library with the requests library. I am well-versed in pneumatic system designs using Festo FluidSim and have worked on integrating chatbots like GPT-3.5 into my projects using prompt engineering.

Moreover, I have hands-on experience in using the Godot game engine and can create macros and basic game bots. I am skilled in image processing with OpenCV, which has been instrumental in many of my projects.

If you're looking for a dedicated and passionate software engineer who is always eager to learn and explore new technologies, look no further. I would love to work with you and help you bring your ideas to life!
For more information about my education, experience, and skills, please feel free to check out my LinkedIn profile at. """
    link = "https://www.linkedin.com/in/seymen-ege-özseymen-910355230/"
    text2 = "There you can find more details about my background in software engineering and the various projects I've worked on. I look forward to connecting with you there!"
    context = {"text":text,"text2":text2,"link":link}
    return render(request,"about.html",context)

def simulate(request):
    form = SimForm(request.POST or None,request.FILES or None)
    if request.POST:
        if form.is_valid():
            edge = float(form["Cutting_Tool_Diameter"].value())
            maxX = 0
            maxY = 0
            lines = ""
            for line in request.FILES["file"]:
                lines += line.decode()

            lines = lines.split("\n")
            for line in lines:
                if line.startswith("G01") and "X" in line:
                    lineList = line.split(" ")
                    if float(lineList[1][1:]) > maxX:
                        maxX = float(lineList[1][1:])
                    if len(lineList) > 2:
                        if float(lineList[2][1:]) > maxY:
                            maxY = float(lineList[2][1:])

            xMulti = 0
            yMulti = 0
            while (len(str(maxX).split("."))) > 1 and str(maxX).split(".")[1] != "0":
                xMulti += 1
                maxX *= 10
            while (len(str(maxY).split("."))) > 1 and str(maxY).split(".")[1] != "0":
                yMulti += 1
                maxY *= 10

            while yMulti > xMulti:
                xMulti += 1
                maxX *= 10

            while xMulti > yMulti:
                yMulti += 1
                maxY *= 10

            if xMulti > 0:
                edge *= xMulti*10

            maxX = int(maxX)
            maxY = int(maxY)

            img = np.zeros((maxY,maxX))

            x1 = 0
            y1 = 0
            lineStart = False
            for line in lines:
                if line.startswith("G01") and "X" in line:
                    lineList = line.split(" ")
                    if xMulti > 0:
                        x2 = int(float(lineList[1][1:])*(xMulti*10))
                    else:
                        x2 = int(float(lineList[1][1:]))

                    if len(lineList) > 2:
                        if yMulti > 0:
                            y2 = maxY - int(float(lineList[2][1:])*(yMulti*10))
                        else:
                            y2 = maxY - int(float(lineList[2][1:]))
                    if lineStart:
                        cv2.line(img,(x1,y1),(x2,y2),(255,255,255),int(math.ceil(edge)))
                    lineStart = True
                    x1 = x2
                    y1 = y2
                elif line.startswith("G00"):
                    lineStart = False
            retval, buffer = cv2.imencode('.jpg', img)
            jpg_as_text = base64.b64encode(buffer)
            img = str(jpg_as_text)[2:]
            img = list(img)
            img.pop()
            img = "".join(img)
            return render(request,"simulation.html",{"form":form,"img":img})
    
    return render(request,"simulation.html",{"form":form})