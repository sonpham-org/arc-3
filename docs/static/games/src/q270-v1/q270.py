"""q270 Circuit Cautery -- distinguish timed causal circuits with reversible clamps."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BOARD,CLAMP,WIRE,PULSE,MODEL,BAD=2,13,11,10,15,14,8
LEVELS=[
 {"name":"Open Lead","model":0,"plan":(1,4)},
 {"name":"Delayed Gate","model":2,"plan":(2,4,1,4)},
 {"name":"Cautered Fork","model":4,"plan":(1,2,4,3,4)},
 {"name":"Reversible Clamp","model":1,"plan":(3,4,3,2,4)},
 {"name":"Pulse Contrast","model":3,"plan":(1,4,2,3,4,1,4)},
 {"name":"Circuit Cautery","model":5,"plan":(2,1,4,3,4,1,2,4)}]
def tick(signal,mask,clock,model):
 parent=model%3;invert=model//3;bit=((mask>>parent)&1)^invert
 return (signal+bit+clock)%4
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=BOARD
  for i in range(3):
   x=9+i*17;f[11:21,x:x+10]=CLAMP if g.mask&(1<<i) else WIRE
  for i,v in enumerate(g.pulses[-5:]):f[29+i*5:33+i*5,8:8+v*11]=PULSE
  f[53:57,8:8+g.candidate*8]=MODEL
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q270(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.mask=self.signal=self.clock=self.candidate=0;self.history=[];self.pulses=[];self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q270",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.mask=self.signal=self.clock=self.candidate=0;self.history=[];self.pulses=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.mask^=1<<(a-1);self.history.append(a)
  elif a==4:self.signal=tick(self.signal,self.mask,self.clock,x["model"]);self.pulses.append(self.signal);self.clock=(self.clock+1)%4;self.mask=0;self.history.append(a)
  elif a==5:self.candidate=(self.candidate+1)%6
  elif a==6:
   if tuple(self.history)==x["plan"] and self.candidate==x["model"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
