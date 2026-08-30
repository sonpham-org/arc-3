"""q728 Asterism Gradient -- conserve influence across a phased distribution and reset."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CHART,STAR,INFLUENCE,PHASE,EVIDENCE,TARGET,BAD=12,3,9,15,10,14,6,8
LEVELS=[
 {"name":"Conserved Influence","start":[2,1,0],"target":[1,1,1],"target_phase":1,"probe":3,"evidence":False},
 {"name":"Capacity and Phase","start":[3,0,1],"target":[1,2,1],"target_phase":2,"probe":6,"evidence":True},
 {"name":"Gradient Threshold","start":[1,3,0],"target":[2,0,2],"target_phase":1,"probe":5,"evidence":True},
 {"name":"Experiment Then Execute","start":[4,0,1],"target":[1,2,2],"target_phase":3,"probe":7,"evidence":True},
 {"name":"Precessing Relation","start":[2,3,1],"target":[3,1,2],"target_phase":2,"probe":8,"evidence":True},
 {"name":"Asterism Gradient","start":[5,1,1],"target":[2,2,3],"target_phase":3,"probe":9,"evidence":True}]
def influence(v):return sum(i*x for i,x in enumerate(v))
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=CHART
  for i,v in enumerate(g.values):x=9+i*17;f[18:42,x:x+11]=STAR;f[37-v*4:39,x+3:x+8]=INFLUENCE;f[45:49,x:x+11]=TARGET if v==g.target[i] else CHART
  f[3:6,8:8+g.phase*10]=PHASE
  if g.evidence:f[50:53,8:30]=EVIDENCE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q728(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.start=self.values=self.target=[];self.target_phase=self.probe=self.cursor=self.phase=0;self.require_evidence=self.evidence=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q728",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.start=list(s["start"]);self.values=list(self.start);self.target=list(s["target"]);self.target_phase=s["target_phase"];self.probe=s["probe"];self.require_evidence=s["evidence"];self.cursor=self.phase=0;self.evidence=self.failed=False
 def step(self):
  z=self.action.id.value;nxt=(self.cursor+1)%3
  if z==0:self.complete_action();return
  if z==1 and self.values[self.cursor]>0:self.values[self.cursor]-=1;self.values[nxt]+=1
  elif z==2 and self.values[nxt]>0:self.values[nxt]-=1;self.values[self.cursor]+=1
  elif z==3:self.cursor=nxt
  elif z==4:self.phase=(self.phase+1)%4
  elif z==5 and not self.evidence:
   if influence(self.values)>=self.probe:self.evidence=True;self.values=list(self.start);self.cursor=self.phase=0
   else:self.failed=True;self.lose()
  elif z==6:
   if self.values==self.target and self.phase==self.target_phase and (self.evidence or not self.require_evidence):self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
