"""q656 Palimpsest Analogy -- transfer a relation between transformed archives."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,INK,SOURCE,TARGET,FAILED,CURSOR=6,10,12,14,11,8,15
BASE=[1,3,2,4]
LEVELS=[
 {"name":"Copied Margins","source":[1,2,3,4],"target":[2,3,4,1],"failed":[2,4,3,1]},
 {"name":"Rebound Folio","source":[2,4,1,3],"target":[4,1,3,2],"failed":[4,1,2,3]},
 {"name":"Scraped Ink","source":[3,1,4,2],"target":[1,4,2,3],"failed":[1,3,2,4]},
 {"name":"False Analogy","source":[4,2,3,1],"target":[3,1,4,2],"failed":[3,2,4,1]},
 {"name":"Structural Echo","source":[2,3,1,4],"target":[4,2,1,3],"failed":[4,2,3,1]},
 {"name":"Palimpsest Analogy","source":[3,4,2,1],"target":[2,1,3,4],"failed":[2,3,1,4]}]
def route(mapping):return [mapping[x-1] for x in BASE]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;l=LEVELS[g.level_index];f[:,:]=BG;f[6:58,5:59]=ARCHIVE
  for row,(seq,col) in enumerate(((route(l["source"]),SOURCE),(route(l["target"]),TARGET),(l["failed"],FAILED))):
   y=13+row*14
   for i,v in enumerate(seq):x=9+i*12;f[y:y+7,x:x+7]=col;f[y+2:y+5,x+2:x+2+v]=INK
  y=13+g.phase*14;f[y-2:y+9,7+g.index*12:9+g.index*12]=CURSOR
  if g.bad:f[60:63,20:44]=FAILED
  return f
class Q656(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.phase=self.index=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q656",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):self.phase=self.index=0;self.bad=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  l=LEVELS[self.level_index];mapping=l["source"] if self.phase==0 else l["target"]
  if z!=route(mapping)[self.index]:self.bad=True;self.lose()
  else:
   self.index+=1
   if self.index==len(BASE):
    if self.phase==0:self.phase=1;self.index=0
    else:self.next_level()
  self.complete_action()
