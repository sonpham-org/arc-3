"""q017 Mimic or Seeker -- distinguish copied motion from goal-directed motion."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,AGENT,MIMIC,SEEKER,GOAL,CURSOR,BAD=15,1,10,12,9,14,11,8
LEVELS=[
 {"name":"Copy or Goal","roles":"ms","dirs":[0,4],"target":1,"goal":4},
 {"name":"Second Response","roles":"mss","dirs":[0,2,4],"target":2,"goal":4},
 {"name":"Shared Motion","roles":"msm","dirs":[0,3,0],"target":1,"goal":3},
 {"name":"Latent Destination","roles":"smss","dirs":[2,0,1,4],"target":3,"goal":4},
 {"name":"Crowd Test","roles":"mmsss","dirs":[0,0,2,3,4],"target":4,"goal":4},
 {"name":"Mimic or Seeker","roles":"msmsss","dirs":[0,2,0,1,4,3],"target":4,"goal":4}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=FIELD;n=len(g.roles)
  for i in range(n):
   x=7+i*(49//n);f[24:35,x:x+7]=AGENT;f[17:20,x:x+7]=CURSOR if i==g.cursor else FIELD
   if g.revealed:
    r=g.last_probe if g.roles[i]=="m" else g.dirs[i];f[38:43,x:x+min(7,r+2)]=MIMIC if g.roles[i]=="m" else SEEKER
  f[47:52,8:8+g.goal*8]=GOAL
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q017(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.roles="";self.dirs=[];self.target=self.goal=self.cursor=self.last_probe=0;self.revealed=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q017",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.roles=s["roles"];self.dirs=list(s["dirs"]);self.target=s["target"];self.goal=s["goal"];self.cursor=self.last_probe=0;self.revealed=self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.last_probe=a;self.revealed=True
  elif a==5:self.cursor=(self.cursor+1)%len(self.roles)
  elif a==6:
   if self.revealed and self.cursor==self.target and self.roles[self.cursor]=="s" and self.dirs[self.cursor]==self.goal:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
