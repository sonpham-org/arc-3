"""q210 Aurora Parallax -- track physical bands through a polar observation frame."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SKY,BAND,GLOW,POLE,VIEW,BAD=0,9,15,10,12,11,8
LEVELS=[{"name":n,"span":s,"plan":p} for n,s,p in [
 ("First Arc",5,(3,1,3)),("Turned Horizon",6,(2,3,1,3)),("Polar Reversal",7,(1,3,2,3,1)),
 ("Triple Curtain",8,(2,1,3,3,2,1)),("Aurora Phase",9,(3,1,2,3,1,3,2)),
 ("Aurora Parallax",10,(2,3,1,2,3,3,1,2))]]
def advance(state,a,span):
 bands,view,pole=state;v=list(bands)
 if a==1:view=(view+1)%3
 elif a==2:pole=1-pole
 else:
  physical=(view+(1 if pole else 2))%3;delta=-1 if pole^(view%2) else 1;v[physical]=(v[physical]+delta)%span
 return tuple(v),view,pole
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SKY
  for i,v in enumerate(g.bands):
   y=12+i*12;f[y:y+7,7:57]=BAND;f[y:y+7,7+v*4:12+v*4]=GLOW
  f[49:53,8:8+g.view*14]=VIEW;f[54:58,43:56]=POLE if g.pole else GLOW
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q210(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bands=(0,2,4);self.view=self.pole=0;self.target=None;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q210",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.bands=(0,2,4);self.view=self.pole=0;s=(self.bands,0,0)
  for a in x["plan"]:s=advance(s,a,x["span"])
  self.target=s;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.bands,self.view,self.pole=advance((self.bands,self.view,self.pole),a,x["span"])
  elif a==6:
   if (self.bands,self.view,self.pole)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
