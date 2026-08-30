"""q205 Alloy Veil -- occluded billet updates in a moving force frame."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,BILLET,FORCE,SEEN,HIDDEN,FRAME,BAD=1,7,12,14,15,10,6,8
LEVELS=[{"name":n,"size":s,"plan":p} for n,s,p in [("Hidden Billet",4,[2,1,2]),("Translated Lane",5,[2,3,1,2]),("Rotated Force",6,[1,2,3,2,2]),("Coupled Regions",7,[2,1,3,2,1,2]),("Edge Alignment",8,[1,2,2,3,1,2,1]),("Alloy Veil",9,[2,1,3,2,2,1,2,3])]]
def advance(s,z,n):
 vals,focus,origin,rot=s;v=list(vals)
 if z==1:focus=1-focus
 elif z==3:rot=(rot+1)%4
 else:j=1-focus;d=-1 if rot%2 else 1;v[j]=(v[j]+d+origin)%n
 origin=(origin+1)%n;return tuple(v),focus,origin,rot
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=FOUNDRY
  for i,v in enumerate(g.vals):x=9+i*32;f[14:29,x:x+14]=SEEN if i==g.focus else HIDDEN;f[32:36,x:x+v*2]=BILLET
  f[42:46,8:8+g.origin*5]=FORCE;f[51:55,8:8+g.rot*11]=FRAME
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q205(ARCBaseGame):
 def __init__(self):self.display=D(self);self.vals=(0,1);self.focus=self.origin=self.rot=0;self.target=None;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q205",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.vals=(0,1);self.focus=self.origin=self.rot=0;s=(self.vals,0,0,0)
  for z in x["plan"]:s=advance(s,z,x["size"])
  self.target=s;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2,3):self.vals,self.focus,self.origin,self.rot=advance((self.vals,self.focus,self.origin,self.rot),z,x["size"])
  elif z==6:
   if (self.vals,self.focus,self.origin,self.rot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
