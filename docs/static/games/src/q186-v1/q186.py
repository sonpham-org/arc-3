"""q186 Deferred Mirror -- actions appear in a remote region only after a countdown."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ROOM,LOCAL,REMOTE,QUEUE,TARGET,DONE,BAD=6,1,9,12,15,14,10,8
LEVELS=[
 {"name":"Visible Countdown","delay":1,"target":[1,4]}, {"name":"Reserve the Echo","delay":2,"target":[2,3,1]},
 {"name":"Remote Mirror","delay":2,"target":[4,1,3,2]}, {"name":"Deferred Space","delay":3,"target":[1,3,2,4,1]},
 {"name":"Long Credit","delay":3,"target":[3,1,4,2,3,1]}, {"name":"Deferred Mirror","delay":4,"target":[2,4,1,3,2,1,4]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=ROOM;f[15:35,8:28]=LOCAL;f[15:35,36:56]=REMOTE
  for i,(d,a) in enumerate(g.queue):f[39+i*3:41+i*3,8:8+d*7]=QUEUE
  for i,t in enumerate(g.target):x=8+i*7;f[49:54,x:x+5]=DONE if i<g.progress else TARGET
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q186(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.target=[];self.delay=self.progress=0;self.queue=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q186",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.target=list(s["target"]);self.delay=s["delay"];self.progress=0;self.queue=[];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  self.queue=[(d-1,a) for d,a in self.queue]
  ready=[a for d,a in self.queue if d<=0];self.queue=[(d,a) for d,a in self.queue if d>0]
  for a in ready:
   if a!=self.target[self.progress]:self.failed=True;self.lose();break
   self.progress+=1
   if self.progress==len(self.target):self.next_level();self.complete_action();return
  if z in (1,2,3,4):self.queue.append((self.delay,z))
  self.complete_action()
