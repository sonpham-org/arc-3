"""q079 Exception Signal -- retain a general rule while honoring marked local inversions."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ROAD,COMMAND,EXCEPTION,NORMAL,RESPONSE,DONE,BAD=13,1,9,14,10,12,6,8
LEVELS=[
 {"name":"One Exception","commands":[1,2],"exceptions":[False,True]},
 {"name":"Keep the Rule","commands":[4,1,3],"exceptions":[False,True,False]},
 {"name":"Rare Marker","commands":[2,3,1,4],"exceptions":[False,False,True,False]},
 {"name":"Local Revision","commands":[1,4,2,3,1],"exceptions":[True,False,False,True,False]},
 {"name":"Do Not Overcorrect","commands":[3,2,4,1,2,3],"exceptions":[False,True,False,False,True,False]},
 {"name":"Exception Signal","commands":[1,3,4,2,1,4,2],"exceptions":[False,False,True,False,True,False,False]}]
def response(command,exception):return 5-command if exception else command
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=ROAD;k=min(g.progress,len(g.commands)-1);f[18:28,10:10+g.commands[k]*8]=COMMAND;f[32:39,10:54]=EXCEPTION if g.exceptions[k] else NORMAL
  for i in range(len(g.commands)):x=8+i*7;f[45:51,x:x+5]=DONE if i<g.progress else RESPONSE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q079(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.commands=self.exceptions=[];self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q079",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.commands=list(s["commands"]);self.exceptions=list(s["exceptions"]);self.progress=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z!=response(self.commands[self.progress],self.exceptions[self.progress]):self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.commands):self.next_level()
  self.complete_action()
