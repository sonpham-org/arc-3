"""q269 Mycelium Override -- identify temporal causal networks through staged nutrient pulses."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BED,NUTRIENT,HYPHA,EFFECT,MODEL,BAD=2,7,11,15,14,6,8
LEVELS=[{"name":n,"model":m,"plan":p} for n,m,p in [
 ("First Pulse",0,(1,4)),("Delayed Branch",2,(2,4,1,4)),
 ("Collider Bed",4,(1,2,4,3,4)),("Temporal Override",1,(3,4,2,1,4)),
 ("Network Contrast",3,(1,4,2,3,4,1,4)),("Mycelium Override",5,(3,1,4,2,4,1,3,4))]]
def evolve(effect,mask,last,model):
 parent=model%3;pol=model//3;signal=((mask>>parent)&1)^pol
 return (effect+signal+last+parent)%4
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=BED
  for i in range(3):
   x=9+i*17;f[11:21,x:x+10]=NUTRIENT if g.mask&(1<<i) else HYPHA
  for i,v in enumerate(g.effects[-5:]):f[28+i*5:32+i*5,8:8+v*11]=EFFECT
  f[53:57,8:8+g.candidate*8]=MODEL
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q269(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.mask=self.last=self.effect=self.candidate=0;self.history=[];self.effects=[];self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q269",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.mask=self.last=self.effect=self.candidate=0;self.history=[];self.effects=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.mask^=1<<(a-1);self.last=a;self.history.append(a)
  elif a==4:self.effect=evolve(self.effect,self.mask,self.last,x["model"]);self.effects.append(self.effect);self.mask=0;self.history.append(a)
  elif a==5:self.candidate=(self.candidate+1)%6
  elif a==6:
   if tuple(self.history)==x["plan"] and self.candidate==x["model"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
