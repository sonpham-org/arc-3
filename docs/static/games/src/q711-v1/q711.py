"""q711 Aurora Gradient -- cross a continuous-looking threshold under phase and hysteresis."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SKY,CURTAIN,MOTE,GRADIENT,PHASE,CAPACITY,BAD=7,9,12,15,14,11,10,8
LEVELS=[
 {"name":"First Gradient","plan":(1,3),"threshold":1},{"name":"Return Hysteresis","plan":(1,2,3,1),"threshold":2},
 {"name":"Phase Capacity","plan":(4,1,3,2,1),"threshold":3},{"name":"Sweeping Curtain","plan":(1,1,3,4,2,3),"threshold":4},
 {"name":"Coupled Influence","plan":(2,1,4,3,1,2,3),"threshold":5},{"name":"Aurora Gradient","plan":(1,3,2,4,1,1,3,2),"threshold":6}]
def advance(s,a):
 bins,phase,capacity,direction,influence=s;b=list(bins)
 if a==1:
  if b[0]:b[0]-=1;b[1]+=1;direction=1;influence=(influence+capacity+phase+1)%9
 elif a==2:
  if b[1]:b[1]-=1;b[2]+=1;direction=2;influence=(influence+2*capacity+phase+direction)%9
 elif a==3:phase=(phase+1)%4;influence=(influence+direction)%9
 else:capacity=1+capacity%3;influence=(influence+capacity)%9
 return tuple(b),phase,capacity,direction,influence
def target(x):
 s=((6,0,0),0,1,0,0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SKY
  for i,v in enumerate(g.bins):
   x=8+i*17;f[11:39,x:x+11]=CURTAIN;f[36-v*4:37,x+2:x+9]=MOTE
  f[43:48,8:8+g.influence*5]=GRADIENT;f[50:53,8:8+g.phase*11]=PHASE;f[55:59,8:8+g.capacity*12]=CAPACITY
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q711(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bins=(6,0,0);self.phase=0;self.capacity=1;self.direction=self.influence=self.threshold=0;self.target=target(LEVELS[0]);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q711",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.bins=(6,0,0);self.phase=0;self.capacity=1;self.direction=self.influence=self.threshold=0;self.target=target(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.bins,self.phase,self.capacity,self.direction,self.influence=advance((self.bins,self.phase,self.capacity,self.direction,self.influence),a)
  elif a==5:self.threshold=(self.threshold+1)%7
  elif a==6:
   if (self.bins,self.phase,self.capacity,self.direction,self.influence)==self.target and self.threshold==x["threshold"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
