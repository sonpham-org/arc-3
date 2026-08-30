"""q207 Shadow Orchard -- recover fruit motion from observer-relative shadows."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,FRUIT,SHADOW,SUN,OBSERVER,BAD=0,14,8,4,11,15,3
LEVELS=[{"name":n,"span":s,"plan":p} for n,s,p in [
 ("Morning Shadow",5,(3,1,3)),("Changed View",6,(1,3,2,3)),
 ("Noon Occlusion",7,(2,3,1,3,2)),("Three Tree Parallax",8,(1,3,3,2,1,3)),
 ("Long Shadow",9,(2,1,3,2,3,1,3)),("Shadow Orchard",10,(3,2,1,3,1,2,3,3))]]
def advance(state,a,span):
 pos,observer,sun=state;p=list(pos)
 if a==1:observer=(observer+1)%3
 elif a==2:sun=(sun+1)%4
 else:
  hidden=(observer+sun+1)%3;p[hidden]=(p[hidden]+(1 if sun<2 else -1))%span
 return tuple(p),observer,sun
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=ORCHARD
  for i,p in enumerate(g.pos):
   x=8+p*5;y=12+i*13;f[y:y+7,x:x+7]=FRUIT;off=(g.sun-1)*2;f[y+8:y+11,max(5,x+off):min(59,x+7+off)]=SHADOW
  f[50:55,7:7+g.sun*11]=SUN;f[55:59,44:44+g.observer*5]=OBSERVER
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q207(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.pos=(0,2,4);self.observer=self.sun=0;self.target=None;self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q207",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.pos=(0,2,4);self.observer=self.sun=0;s=(self.pos,0,0)
  for a in x["plan"]:s=advance(s,a,x["span"])
  self.target=s;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.pos,self.observer,self.sun=advance((self.pos,self.observer,self.sun),a,x["span"])
  elif a==6:
   if (self.pos,self.observer,self.sun)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
