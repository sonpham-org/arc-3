"""q208 Mirror Lanterns -- track physical lights through a changing reflected frame."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,PAVILION,LIGHT,MIRROR,VIEW,TRACE,BAD=0,15,11,9,12,14,8
LEVELS=[
 {"name":"Single Reflection","span":5,"plan":(3,1,3)},
 {"name":"Turned Pavilion","span":6,"plan":(2,3,1,3)},
 {"name":"Reverse Image","span":7,"plan":(1,3,2,3,1)},
 {"name":"Coupled Mirrors","span":8,"plan":(2,1,3,3,2,1)},
 {"name":"Lantern Parity","span":9,"plan":(3,1,2,3,1,3,2)},
 {"name":"Mirror Lanterns","span":10,"plan":(2,3,1,2,3,3,1,2)}]
def advance(state,a,span):
 lights,view,mirror=state;v=list(lights)
 if a==1:view=(view+1)%4
 elif a==2:mirror=1-mirror
 else:
  apparent=(view+(3 if mirror else 1))%4;physical=3-apparent if mirror else apparent
  v[physical]=(v[physical]+(1 if (view+mirror)%2==0 else -1))%span
 return tuple(v),view,mirror
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=PAVILION;f[8:55,30:34]=MIRROR
  for i,p in enumerate(g.lights):
   x=7+(i%2)*36+p*2;y=13+(i//2)*24;f[y:y+7,x:x+7]=LIGHT
  f[49:53,7:7+g.view*10]=VIEW;f[55:58,42:56]=TRACE if g.mirror else MIRROR
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q208(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.lights=(0,1,2,3);self.view=self.mirror=0;self.target=None;self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q208",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.lights=(0,1,2,3);self.view=self.mirror=0;s=(self.lights,0,0)
  for a in x["plan"]:s=advance(s,a,x["span"])
  self.target=s;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.lights,self.view,self.mirror=advance((self.lights,self.view,self.mirror),a,x["span"])
  elif a==6:
   if (self.lights,self.view,self.mirror)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
