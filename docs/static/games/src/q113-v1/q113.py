"""q113 Alternating Teacher -- infer which context selects which demonstrated tutor."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,PANEL,TUTORA,TUTORB,CONTEXT,DONE,BAD=4,1,9,12,11,14,8
LEVELS=[
 {"name":"Two Tutors","a":[1,2,3,4],"b":[2,1,4,3],"items":[(0,0),(1,1)]},
 {"name":"Alternation","a":[4,3,2,1],"b":[1,3,4,2],"items":[(0,1),(1,2),(0,3)]},
 {"name":"Context Switch","a":[2,4,1,3],"b":[3,1,4,2],"items":[(1,0),(1,3),(0,2),(1,1)]},
 {"name":"Mixed Lesson","a":[3,2,4,1],"b":[1,4,2,3],"items":[(0,0),(1,2),(1,1),(0,3),(1,0)]},
 {"name":"Delayed Tutor","a":[4,1,3,2],"b":[2,3,1,4],"items":[(1,3),(0,2),(0,0),(1,1),(0,3),(1,2)]},
 {"name":"Alternating Teacher","a":[1,3,2,4],"b":[4,2,3,1],"items":[(0,2),(1,0),(0,3),(1,1),(1,2),(0,0),(1,3)]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[6:26,4:60]=PANEL
  for row,(policy,c) in enumerate(((g.a,TUTORA),(g.b,TUTORB))):
   for i,v in enumerate(policy):f[10+row*9:16+row*9,8+i*13:16+i*13]=c;f[12+row*9:14+row*9,9+i*13:9+i*13+v]=CONTEXT
  for i,(teacher,signal) in enumerate(g.items):x=7+i*8;f[36:43,x:x+6]=TUTORA if teacher==0 else TUTORB;f[46:52,x:x+6]=DONE if i<g.progress else CONTEXT;f[47:49,x:x+signal+2]=PANEL
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q113(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.a=self.b=[];self.items=[];self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q113",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.a=list(s["a"]);self.b=list(s["b"]);self.items=list(map(tuple,s["items"]));self.progress=0;self.failed=False
 def step(self):
  act=self.action.id.value
  if act==0:self.complete_action();return
  teacher,signal=self.items[self.progress];expected=(self.a if teacher==0 else self.b)[signal]
  if act!=expected:self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.items):self.next_level()
  self.complete_action()
