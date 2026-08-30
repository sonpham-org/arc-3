"""q189 Inheritance -- current work passes resources and damage to a successor."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SITE,CURRENT,SUCCESSOR,RESOURCE,DAMAGE,WORK,BAD=11,2,9,12,14,8,10,6
LEVELS=[
 {"name":"Leave Enough","initial":5,"work":2,"need":2,"max_damage":1,"salvage":False},
 {"name":"Repair the Legacy","initial":6,"work":2,"need":2,"max_damage":0,"salvage":False},
 {"name":"Successor Budget","initial":7,"work":3,"need":2,"max_damage":1,"salvage":False},
 {"name":"Salvaged Structure","initial":6,"work":3,"need":2,"max_damage":1,"salvage":True},
 {"name":"Intergenerational Plan","initial":9,"work":4,"need":3,"max_damage":1,"salvage":True},
 {"name":"Inheritance","initial":12,"work":5,"need":3,"max_damage":0,"salvage":True}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=SITE;f[15:29,8:22]=CURRENT;f[15:29,42:56]=SUCCESSOR;f[35:39,8:8+g.resource*5]=RESOURCE;f[43:47,8:8+g.damage*8]=DAMAGE;f[50:54,8:8+g.progress*8]=WORK
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q189(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.resource=self.work=self.need=self.max_damage=self.progress=self.damage=0;self.allow_salvage=self.salvaged=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q189",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.resource=s["initial"];self.work=s["work"];self.need=s["need"];self.max_damage=s["max_damage"];self.allow_salvage=s["salvage"];self.progress=self.damage=0;self.salvaged=self.failed=False
 def spend(self,n):
  self.resource-=n
  if self.resource<0:self.failed=True;self.lose();return False
  return True
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1 and self.progress<self.work:
   if self.spend(1):self.progress+=1;self.damage+=1
  elif z==2 and self.progress<self.work:
   if self.spend(2):self.progress+=1
  elif z==3:
   if self.spend(1):self.damage=max(0,self.damage-1)
  elif z==4 and self.allow_salvage and not self.salvaged:self.resource+=2;self.damage+=1;self.salvaged=True
  elif z==5:
   if self.progress==self.work and self.resource>=self.need and self.damage<=self.max_damage:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
