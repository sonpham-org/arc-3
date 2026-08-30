"""q115 Partial Demonstration -- reconstruct latent subgoals between shown endpoints."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,START,END,HIDDEN,STATE,DONE,BAD=4,1,9,14,3,10,12,8
LEVELS=[
 {"name":"Missing Middle","start":0,"end":3,"mod":5}, {"name":"Two Subgoals","start":1,"end":0,"mod":6},
 {"name":"Wrapped Path","start":4,"end":2,"mod":7}, {"name":"Latent Sequence","start":2,"end":7,"mod":8},
 {"name":"Long Gap","start":5,"end":1,"mod":9}, {"name":"Partial Demonstration","start":3,"end":9,"mod":10}]
def apply(x,a,m):return (x+(1 if a==1 else 2 if a==2 else -1 if a==3 else 3))%m
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:55,4:60]=FIELD;f[18:30,8:18]=START;f[18:30,46:56]=END;f[21:27,11:11+g.start]=STATE;f[21:27,49:49+g.end]=STATE;f[34:42,22:42]=HIDDEN;f[45:50,8:8+g.steps*6]=DONE
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q115(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.start=self.end=self.mod=self.value=self.steps=0;self.budget=8;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q115",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.start=s["start"];self.end=s["end"];self.mod=s["mod"];self.value=self.start;self.steps=0;self.budget=5+self.level_index;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.value=apply(self.value,a,self.mod);self.steps+=1;self.budget-=1
  elif a==6:
   if self.value==self.end and self.steps>0:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  if self.budget<=0 and self.value!=self.end:self.failed=True;self.lose()
  self.complete_action()
