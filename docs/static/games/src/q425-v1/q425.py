"""q425 Ember Doctrine -- bank samples across a heat-triggered law change."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,EMBER,HEAT,SAMPLE,BANK,RULE,BAD=9,13,12,11,15,14,10,8
LEVELS=[
 {"name":"First Ember","boundary":1,"old":0,"new":1},
 {"name":"Slow Kiln","boundary":2,"old":1,"new":2},
 {"name":"Quenched Carrier","boundary":3,"old":2,"new":0},
 {"name":"Moving Threshold","boundary":2,"old":0,"new":2},
 {"name":"Banked Doctrine","boundary":4,"old":1,"new":0},
 {"name":"Ember Doctrine","boundary":5,"old":2,"new":1}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=KILN;f[11:18,8:8+g.heat*8]=EMBER
  for i in range(3):f[27:37,10+i*16:21+i*16]=BANK if g.evidence&(1<<i) else SAMPLE
  f[45:50,8:29 if g.quenched else 16]=HEAT;f[53:57,8:8+g.candidate*14]=RULE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q425(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.heat=self.rule=self.sample=self.evidence=self.candidate=0;self.quenched=self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q425",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.heat=0;self.rule=x["old"];self.sample=-1;self.evidence=self.candidate=0;self.quenched=self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:
   self.heat+=1
   if self.heat>=x["boundary"]:self.rule=x["new"]
  elif a==2:self.quenched=True;self.heat=0
  elif a==3:self.sample=self.rule
  elif a==4:
   if self.sample>=0:self.evidence|=1<<self.sample;self.sample=-1
   else:self.bad=True;self.lose()
  elif a==5:self.candidate=(self.candidate+1)%3
  elif a==6:
   need=(1<<x["old"])|(1<<x["new"])
   if self.evidence&need==need and self.quenched and self.candidate==x["new"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
