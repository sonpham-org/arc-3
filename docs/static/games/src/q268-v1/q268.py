"""q268 Rootline Injection -- distinguish delayed causal models with chosen valve trials."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SOIL,ROOT,VALVE,READING,MODEL,BAD=10,7,3,14,5,15,8
LEVELS=[{"name":n,"model":m,"experiments":e} for n,m,e in [
 ("Single Valve",0,((1,),)),("Polarity Split",3,((1,),(2,))),
 ("Sibling Roots",1,((2,),(3,))),("Delayed Fork",4,((1,2),(3,))),
 ("Intervention Grid",2,((1,),(2,3),(1,3))),("Rootline Injection",5,((1,2),(2,3),(1,3),(1,2,3)))]]
def response(model,mask):
 parent=model%3;polarity=model//3
 return (((mask>>parent)&1)^polarity)&1
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SOIL
  for i in range(3):
   x=10+i*17;f[10:20,x:x+9]=VALVE if g.mask&(1<<i) else ROOT
  for i,(_,v) in enumerate(g.evidence[-5:]):f[29+i*5:33+i*5,9:25 if v else 17]=READING
  f[52:56,8:8+g.candidate*8]=MODEL
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q268(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.mask=self.candidate=0;self.evidence=[];self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q268",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.mask=self.candidate=0;self.evidence=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.mask^=1<<(a-1)
  elif a==4:self.evidence.append((self.mask,response(x["model"],self.mask)));self.mask=0
  elif a==5:self.candidate=(self.candidate+1)%6
  elif a==6:
   required={sum(1<<(z-1) for z in trial) for trial in x["experiments"]}
   if required.issubset({m for m,_ in self.evidence}) and self.candidate==x["model"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
