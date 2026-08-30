"""q426 Monsoon Edict -- bank law samples across a rain-triggered revision."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TERRACE,RAIN,CLOUD,SAMPLE,BANK,RULE,BAD=9,10,15,12,11,14,6,8
LEVELS=[
 {"name":"First Rain","boundary":1,"old":0,"new":1},{"name":"Late Cloud","boundary":2,"old":1,"new":2},
 {"name":"Drained Carrier","boundary":3,"old":2,"new":0},{"name":"Moving Monsoon","boundary":2,"old":0,"new":2},
 {"name":"Banked Edict","boundary":4,"old":1,"new":0},{"name":"Monsoon Edict","boundary":5,"old":2,"new":1}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=TERRACE;f[11:18,8:8+g.rain*8]=RAIN
  for i in range(3):f[27:37,10+i*16:21+i*16]=BANK if g.evidence&(1<<i) else SAMPLE
  f[45:50,8:29 if g.drained else 16]=CLOUD;f[53:57,8:8+g.candidate*14]=RULE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q426(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.rain=self.rule=self.sample=self.evidence=self.candidate=0;self.drained=self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q426",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.rain=0;self.rule=x["old"];self.sample=-1;self.evidence=self.candidate=0;self.drained=self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:
   self.rain+=1
   if self.rain>=x["boundary"]:self.rule=x["new"]
  elif a==2:self.drained=True;self.rain=0
  elif a==3:self.sample=self.rule
  elif a==4:
   if self.sample>=0:self.evidence|=1<<self.sample;self.sample=-1
   else:self.bad=True;self.lose()
  elif a==5:self.candidate=(self.candidate+1)%3
  elif a==6:
   need=(1<<x["old"])|(1<<x["new"])
   if self.evidence&need==need and self.drained and self.candidate==x["new"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
