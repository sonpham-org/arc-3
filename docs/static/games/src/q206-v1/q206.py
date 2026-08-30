"""q206 Prism Tide -- track hidden drifters through a moving observation lens."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SEA,LENS,DRIFTER,CURRENT,FOAM,BAD=11,9,15,4,12,1,8
LEVELS=[{"name":n,"span":s,"plan":p} for n,s,p in [
 ("Single Refraction",5,[2,3,1]),("Crossing Lens",6,[3,2,2,1]),
 ("Counter Current",7,[1,3,2,3,1]),("Three Body Wake",8,[2,3,1,3,2,1]),
 ("Tidal Parallax",9,[3,1,2,3,2,1,3]),("Prism Tide",10,[2,3,1,1,3,2,3,1])]]
def advance(state,action,span):
 pos,lens,tide=state;p=list(pos)
 if action==1:lens=(lens-1)%3
 elif action==2:lens=(lens+1)%3
 else:
  for i in range(3):
   if i!=lens:p[i]=(p[i]+(1 if (tide+i)%2==0 else -1))%span
 tide=(tide+1)%4
 return tuple(p),lens,tide
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SEA
  for i,p in enumerate(g.pos):
   x=8+p*5;y=13+i*13;f[y:y+7,x:x+7]=LENS if i==g.lens else DRIFTER
  f[50:54,7:7+g.tide*12]=CURRENT
  for x in range(5,60,8):f[7:9,x:x+4]=FOAM
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q206(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.pos=(0,2,4);self.lens=self.tide=0;self.target=None;self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q206",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.pos=(0,2,4);self.lens=self.tide=0;s=(self.pos,0,0)
  for a in x["plan"]:s=advance(s,a,x["span"])
  self.target=s;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.pos,self.lens,self.tide=advance((self.pos,self.lens,self.tide),a,x["span"])
  elif a==6:
   if (self.pos,self.lens,self.tide)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
