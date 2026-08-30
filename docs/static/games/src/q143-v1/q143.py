"""q143 Costly Preview -- spend previews only on consequential uncertain turns."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,STEP,AMBIG,PREVIEW,CURSOR,DONE,BAD=13,1,3,8,10,11,14,5
LEVELS=[
 {"name":"Preview Fork","route":[1,4],"ambiguous":[0],"previews":1},
 {"name":"Save It","route":[4,2,3],"ambiguous":[2],"previews":1},
 {"name":"One Critical Turn","route":[1,4,4,2],"ambiguous":[1],"previews":1},
 {"name":"Two Forks","route":[3,1,4,2,4],"ambiguous":[1,4],"previews":2},
 {"name":"Delayed Preview","route":[2,4,1,3,2,4],"ambiguous":[3,5],"previews":2},
 {"name":"Costly Preview","route":[4,1,3,2,4,2,1],"ambiguous":[2,4,6],"previews":3}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:55,4:60]=FIELD
  for i,a in enumerate(g.route):
   x=8+i*7;c=DONE if i<g.progress else AMBIG if i in g.ambiguous else STEP;f[25:34,x:x+5]=c
   if i==g.progress and g.previewed:f[17+a:20+a,x:x+5]=PREVIEW
  f[3:7,6:6+g.previews*8]=PREVIEW;f[43:48,28:36]=CURSOR+g.selector%2
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q143(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.route=[];self.ambiguous=set();self.progress=self.previews=0;self.selector=1;self.previewed=False;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q143",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.route=list(s["route"]);self.ambiguous=set(s["ambiguous"]);self.progress=0;self.previews=s["previews"];self.selector=1;self.previewed=False;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.selector=(self.selector-2)%4+1;self.previewed=False
  elif a==4:self.selector=self.selector%4+1;self.previewed=False
  elif a==5 and self.previews:self.previews-=1;self.previewed=True
  elif a==6:
   if self.selector!=self.route[self.progress] or (self.progress in self.ambiguous and not self.previewed):self.failed=True;self.lose()
   else:
    self.progress+=1;self.previewed=False
    if self.progress==len(self.route):self.next_level()
  else:self.failed=True;self.lose()
  self.complete_action()
