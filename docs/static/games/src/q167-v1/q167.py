"""q167 Probe or Act -- reduce uncertainty safely before irreversible use."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,OBJECT,PROBE,YES,NO,CURSOR,BAD=7,1,12,10,14,8,15,6
LEVELS=[
 {"name":"Probe Before Use","objects":[0,1],"target":1,"bits":2,"limit":1},
 {"name":"Shrinking Uncertainty","objects":[1,2,3],"target":1,"bits":3,"limit":1},
 {"name":"Two Safe Tests","objects":[0,3,5,6],"target":2,"bits":3,"limit":2},
 {"name":"Irreversible Use","objects":[0,1,2,4,7],"target":4,"bits":3,"limit":2},
 {"name":"Confidence Object","objects":[1,2,4,8,11,13],"target":5,"bits":4,"limit":2},
 {"name":"Probe or Act","objects":[0,3,5,6,9,10,12,15],"target":6,"bits":4,"limit":3}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=LAB
  for i in range(g.bits):x=8+i*12;f[15:27,x:x+9]=PROBE;f[11:14,x:x+9]=CURSOR if i==g.probe else LAB;f[30:34,x:x+9]=YES if i in g.used and g.objects[g.target]&(1<<i) else NO if i in g.used else LAB
  for i in range(len(g.objects)):x=7+i*7;f[43:51,x:x+5]=OBJECT;f[53:56,x:x+5]=CURSOR if i==g.hyp else LAB
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q167(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.objects=[];self.target=self.bits=self.limit=self.probe=self.hyp=0;self.used=set();self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q167",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.objects=list(s["objects"]);self.target=s["target"];self.bits=s["bits"];self.limit=s["limit"];self.probe=self.hyp=0;self.used=set();self.failed=False
 def unique(self):
  t=self.objects[self.target];return all(i==self.target or any(((t>>b)&1)!=((v>>b)&1) for b in self.used) for i,v in enumerate(self.objects))
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.probe=(self.probe-1)%self.bits
  elif z==2:self.probe=(self.probe+1)%self.bits
  elif z==3:self.hyp=(self.hyp-1)%len(self.objects)
  elif z==4:self.hyp=(self.hyp+1)%len(self.objects)
  elif z==5:
   if self.probe not in self.used and len(self.used)<self.limit:self.used.add(self.probe)
   else:self.failed=True;self.lose()
  elif z==6:
   if self.hyp==self.target and self.unique():self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
