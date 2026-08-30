"""q272 Geode Resonance -- identify causal hysteresis from ordered strikes."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CAVERN,CRYSTAL,STRIKE,ECHO,MODEL,BAD=2,7,15,12,14,11,8
LEVELS=[
 {"name":"First Echo","model":0,"plan":(1,4)},{"name":"Lingering Tone","model":2,"plan":(2,4,1,4)},
 {"name":"Crystal Fork","model":4,"plan":(1,2,4,3,4)},{"name":"Hysteresis Loop","model":1,"plan":(3,4,3,2,4)},
 {"name":"Resonance Contrast","model":3,"plan":(1,4,2,3,4,1,4)},{"name":"Geode Resonance","model":5,"plan":(2,1,4,3,4,1,2,4)}]
def tick(signal,mask,last,model):
 parent=model%3;invert=model//3;present=(mask>>parent)&1;memory=(last>>((parent+1)%3))&1
 return (signal+(present^invert)+2*memory+parent)%4
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=CAVERN
  for i in range(3):
   x=9+i*17;f[11:23,x:x+10]=STRIKE if g.mask&(1<<i) else CRYSTAL
  for i,v in enumerate(g.echoes[-5:]):f[30+i*5:34+i*5,8:8+v*11]=ECHO
  f[54:58,8:8+g.candidate*8]=MODEL
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q272(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.mask=self.last=self.signal=self.candidate=0;self.history=[];self.echoes=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q272",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.mask=self.last=self.signal=self.candidate=0;self.history=[];self.echoes=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.mask^=1<<(a-1);self.history.append(a)
  elif a==4:self.signal=tick(self.signal,self.mask,self.last,x["model"]);self.echoes.append(self.signal);self.last=self.mask;self.mask=0;self.history.append(a)
  elif a==5:self.candidate=(self.candidate+1)%6
  elif a==6:
   if tuple(self.history)==x["plan"] and self.candidate==x["model"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
