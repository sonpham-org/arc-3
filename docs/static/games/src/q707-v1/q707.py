"""q707 Spectrum Evidence -- transfer reliability-weighted stopping across two surfaces."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GALLERY,PRISM,PACKET,SAMPLE,SCORE,MEMORY,BAD=6,2,9,12,15,10,14,8
LEVELS=[
 {"name":"Geometry Evidence","sets":[[[0,3],[1,1],[0,2]],[[0,2],[1,1],[0,3]]]},
 {"name":"Agent Transfer","sets":[[[1,2],[0,1],[1,3]],[[1,3],[0,1],[1,2]]]},
 {"name":"Unequal Reliability","sets":[[[0,2],[1,1],[0,4]],[[0,4],[1,1],[0,2]]]},
 {"name":"Safe Stopping","sets":[[[1,3],[0,2],[1,3]],[[1,2],[0,1],[1,4]]]},
 {"name":"Relational Algebra","sets":[[[0,1],[1,2],[0,5]],[[0,4],[1,1],[0,3]]]},
 {"name":"Spectrum Evidence","sets":[[[1,2],[0,1],[1,4],[0,1]],[[1,3],[0,2],[1,4]]]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=GALLERY;f[15:29,8:22]=PRISM if g.phase==0 else PACKET;f[15:29,42:56]=PRISM if g.phase==0 else PACKET;f[34:39,8:8+g.scores[0]*5]=SCORE;f[41:46,8:8+g.scores[1]*5]=SAMPLE
  if g.memory is not None:f[49:53,8:32]=MEMORY
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q707(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.sets=[];self.scores=[0,0];self.phase=self.index=self.cursor=0;self.memory=None;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q707",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,5,6])
 def on_set_level(self,l):self.sets=[[list(x) for x in s] for s in LEVELS[self.level_index]["sets"]];self.scores=[0,0];self.phase=self.index=self.cursor=0;self.memory=None;self.failed=False
 def guaranteed(self):return abs(self.scores[0]-self.scores[1])>sum(w for _,w in self.sets[self.phase][self.index:])
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1 and self.index<len(self.sets[self.phase]):c,w=self.sets[self.phase][self.index];self.scores[c]+=w;self.index+=1
  elif z==2:self.cursor=1-self.cursor
  elif z==5:
   leader=max(range(2),key=lambda i:self.scores[i])
   if not self.guaranteed() or self.cursor!=leader:self.failed=True;self.lose()
   elif self.phase==0:self.memory=leader;self.phase=1;self.index=0;self.scores=[0,0];self.cursor=0
   elif self.memory==leader:self.next_level()
   else:self.failed=True;self.lose()
  elif z==6 and self.phase==1:
   if self.memory==max(range(2),key=lambda i:self.scores[i]) and self.guaranteed():self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
