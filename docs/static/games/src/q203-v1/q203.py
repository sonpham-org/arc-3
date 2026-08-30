"""q203 Ember Veil -- schedule hidden heat updates under one shared fuel rail."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,VESSEL,HEAT,SEEN,HIDDEN,FUEL,BAD=3,13,9,14,15,12,10,8
LEVELS=[
 {"name":"Occluded Firing","n":4,"start":[0,1],"plan":[2,1,2]},
 {"name":"Heat Band","n":5,"start":[1,3],"plan":[2,2,1,2]},
 {"name":"Shared Fuel","n":6,"start":[2,0],"plan":[1,2,1,2,2]},
 {"name":"Repair Tradeoff","n":7,"start":[3,5],"plan":[2,1,2,1,2,2]},
 {"name":"Coupled Vessels","n":8,"start":[6,1],"plan":[1,2,2,1,2,1,2]},
 {"name":"Ember Veil","n":9,"start":[4,7],"plan":[2,1,2,2,1,2,1,2]}]
def tick(values,focus,band,n):
 v=list(values);j=1-focus;v[j]=(v[j]+(1 if band%2==0 else -1))%n;return tuple(v),1-band
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[5:59,4:60]=KILN
  for i,v in enumerate(g.values):x=9+i*32;f[15:31,x:x+14]=SEEN if i==g.focus else HIDDEN;f[34-v*2:38,x:x+14]=VESSEL
  f[43:47,8:8+g.band*20]=HEAT;f[50:54,8:8+g.fuel*5]=FUEL
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q203(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.n=1;self.values=self.target=(0,0);self.focus=self.band=self.fuel=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q203",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.n=x["n"];self.values=tuple(x["start"]);self.focus=self.band=0;self.fuel=len(x["plan"])+1;v=self.values;focus=band=0
  for a in x["plan"]:
   if a==1:focus=1-focus
   else:v,band=tick(v,focus,band,self.n)
  self.target=v;self.bad=False
 def fail(self):self.bad=True;self.lose()
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  self.fuel-=1
  if self.fuel<0:self.fail()
  elif z==1:self.focus=1-self.focus
  elif z==2:self.values,self.band=tick(self.values,self.focus,self.band,self.n)
  elif z==6:
   if self.values==self.target:self.next_level()
   else:self.fail()
  else:self.fail()
  self.complete_action()
