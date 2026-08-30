"""q486 Cloudport Dependency -- satisfy weather-remapped resources across a goal hierarchy."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CLOUD,PORT,RESOURCE,BUILT,WEATHER,BAD=15,10,6,12,14,2,8
LEVELS=[{"name":n,"needs":needs} for n,needs in [
 ("Landing Permit",((0,),)),("Fuel Before Flight",((1,),(0,2))),
 ("Cargo Chain",((2,),(0,1),(1,2))),("Nested Clearance",((0,2),(1,),(0,1,2))),
 ("Storm Hierarchy",((1,2),(0,),(0,2),(0,1))),
 ("Cloudport Dependency",((0,1),(2,),(0,2),(1,),(0,1,2)))]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=CLOUD
  for i in range(len(LEVELS[g.level_index]["needs"])):
   x=7+i*10;f[12:23,x:x+8]=BUILT if i<g.stage else PORT
  for i in sorted(g.bag):f[31+i*7:36+i*7,10:23]=RESOURCE
  f[51:56,8:8+g.weather*15]=WEATHER
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q486(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.stage=self.weather=0;self.bag=set();self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q486",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.stage=self.weather=0;self.bag=set();self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.bag.add((a-1+self.weather)%3)
  elif a==5:self.bag.clear()
  elif a==4:
   if self.stage<len(x["needs"]) and self.bag==set(x["needs"][self.stage]):
    self.stage+=1;self.weather=(self.weather+1)%3;self.bag.clear()
   else:self.bad=True;self.lose()
  elif a==6:
   if self.stage==len(x["needs"]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
