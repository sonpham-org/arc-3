"""q069 Echo Windows -- complementary panes expose immediate and delayed machine effects."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FRAME,LEFT,RIGHT,COMMAND,ECHO,DONE,BAD=7,1,9,12,14,15,10,8
LEVELS=[
 {"name":"One-Step Echo","mapping":[1,2,3,4],"outputs":[1,4]},
 {"name":"Complementary Pane","mapping":[2,3,4,1],"outputs":[1,2,4]},
 {"name":"Delayed Transform","mapping":[4,3,2,1],"outputs":[4,1,3,2]},
 {"name":"Echo Alignment","mapping":[2,1,4,3],"outputs":[3,1,4,2,1]},
 {"name":"Two Views","mapping":[3,4,1,2],"outputs":[4,2,1,3,4,1]},
 {"name":"Echo Windows","mapping":[4,1,2,3],"outputs":[2,4,1,3,2,1,4]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=FRAME;f[15:40,8:29]=LEFT;f[15:40,35:56]=RIGHT;f[22:28,11:11+g.now*4]=COMMAND;f[30:36,38:38+g.echo*4]=ECHO
  for i in range(len(g.outputs)):x=8+i*7;f[47:52,x:x+5]=DONE if i<g.progress else COMMAND
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q069(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.mapping=self.outputs=[];self.progress=self.now=self.echo=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q069",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.mapping=list(s["mapping"]);self.outputs=list(s["outputs"]);self.progress=self.now=self.echo=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  self.echo=self.now;self.now=self.mapping[z-1] if z in (1,2,3,4) else 0
  if self.now!=self.outputs[self.progress]:self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.outputs):self.next_level()
  self.complete_action()
