"""q078 Rotating Contract -- arrangement cues announce cyclic response policies."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,PLAZA,AGENT,CUE,COMMAND,RESPONSE,DONE,BAD=13,1,10,15,12,9,14,8
LEVELS=[
 {"name":"Policy Shift","commands":[1,1],"phases":[0,1]},
 {"name":"Arrangement Cue","commands":[2,4,1],"phases":[1,0,2]},
 {"name":"Three Contracts","commands":[1,3,2,4],"phases":[0,2,1,0]},
 {"name":"Cycle Revision","commands":[4,1,2,3,1],"phases":[2,1,0,2,1]},
 {"name":"Policy Forecast","commands":[2,3,1,4,2,1],"phases":[0,1,2,0,2,1]},
 {"name":"Rotating Contract","commands":[1,4,2,3,1,2,4],"phases":[2,0,1,2,1,0,2]}]
def response(command,phase):return ((command+phase-1)%4)+1
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=PLAZA;k=min(g.progress,len(g.phases)-1)
  for i in range(3):x=12+i*16;h=5+((i+g.phases[k])%3)*4;f[30-h:30,x:x+9]=AGENT;f[33:37,x:x+9]=CUE
  f[41:46,8:8+g.commands[k]*8]=COMMAND
  for i in range(len(g.commands)):x=8+i*7;f[50:54,x:x+5]=DONE if i<g.progress else RESPONSE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q078(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.commands=self.phases=[];self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q078",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.commands=list(s["commands"]);self.phases=list(s["phases"]);self.progress=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z!=response(self.commands[self.progress],self.phases[self.progress]):self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.commands):self.next_level()
  self.complete_action()
