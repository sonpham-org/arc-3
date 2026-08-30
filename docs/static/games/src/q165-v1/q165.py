"""q165 Hypothesis Stack -- preserve candidate rules until evidence supports collapse."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,CANDIDATE,KEPT,DISCARD,EVIDENCE,CURSOR,BAD=12,1,10,14,8,9,11,13
LEVELS=[
 {"name":"Keep Two","count":3,"target":1,"evidence":[3,2]}, {"name":"Delayed Elimination","count":4,"target":2,"evidence":[15,6,4]},
 {"name":"Do Not Collapse","count":4,"target":0,"evidence":[11,9,1]}, {"name":"Stack Revision","count":5,"target":3,"evidence":[31,26,8]},
 {"name":"Recover Candidate","count":5,"target":4,"evidence":[29,21,16]}, {"name":"Hypothesis Stack","count":6,"target":2,"evidence":[63,46,14,4]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=LAB
  for i in range(g.count):x=8+i*8;f[20:39,x:x+6]=KEPT if g.mask&(1<<i) else DISCARD;f[15:18,x:x+6]=CURSOR if i==g.cursor else LAB
  for i in range(len(g.evidence)):f[44:49,8+i*12:17+i*12]=EVIDENCE if i>=g.seen else KEPT
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q165(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.count=self.target=self.cursor=self.mask=self.seen=0;self.evidence=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q165",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[2,3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.count=s["count"];self.target=s["target"];self.evidence=list(s["evidence"]);self.cursor=self.seen=0;self.mask=(1<<self.count)-1;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%self.count
  elif a==4:self.cursor=(self.cursor+1)%self.count
  elif a==2:self.mask&=~(1<<self.cursor)
  elif a==5 and self.seen<len(self.evidence):self.mask&=self.evidence[self.seen];self.seen+=1
  elif a==6:
   if self.seen==len(self.evidence) and self.mask==(1<<self.target) and self.cursor==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
