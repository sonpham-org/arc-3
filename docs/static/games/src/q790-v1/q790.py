"""q790 Vault Rhythm -- transfer two conserved quantities and interrupt an event rhythm."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VAULT,ECHO,STOREA,STOREB,RHYTHM,WINDOW,BAD=14,4,9,10,12,15,6,8
LEVELS=[
 {"name":"Event Window","start":[2,1],"need":[1,1],"period":4,"window":2},
 {"name":"Two Conserved Stores","start":[3,2],"need":[2,1],"period":5,"window":4},
 {"name":"Chunk the Routine","start":[4,2],"need":[2,2],"period":6,"window":1},
 {"name":"Scaled Interval","start":[3,4],"need":[1,3],"period":7,"window":5},
 {"name":"State Defined Interrupt","start":[5,3],"need":[3,2],"period":8,"window":6},
 {"name":"Vault Rhythm","start":[5,5],"need":[3,4],"period":9,"window":7}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=VAULT;f[16:31,8:22]=ECHO;f[16:31,42:56]=ECHO;f[35:39,8:8+g.right[0]*8]=STOREA;f[41:45,8:8+g.right[1]*8]=STOREB;f[49:53,8:8+g.phase*5]=RHYTHM;f[3:6,8:8+g.window*5]=WINDOW
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q790(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.left=self.right=self.need=[];self.period=self.window=self.phase=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q790",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.left=list(s["start"]);self.right=[0,0];self.need=list(s["need"]);self.period=s["period"];self.window=s["window"];self.phase=0;self.failed=False
 def advance(self,n):self.phase=(self.phase+n)%self.period
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2):
   i=z-1
   if self.left[i]<=0:self.failed=True;self.lose()
   else:self.left[i]-=1;self.right[i]+=1;self.advance(1)
  elif z==4:self.advance(3)
  elif z==5:self.advance(1)
  elif z==3:
   if self.right==self.need and self.phase==self.window:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
