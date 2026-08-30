"""q184 Seeded Weather -- early placements determine hazards after delayed seasons."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,SEED,WEATHER,SAFE,TARGET,CURSOR,BAD=1,10,14,9,6,12,11,8
LEVELS=[
 {"name":"One Seed","plots":3,"target":1,"seasons":2}, {"name":"Delayed Rain","plots":4,"target":5,"seasons":2},
 {"name":"Two Hazards","plots":5,"target":10,"seasons":3}, {"name":"Season Chain","plots":5,"target":21,"seasons":3},
 {"name":"Weather Field","plots":6,"target":38,"seasons":4}, {"name":"Seeded Weather","plots":7,"target":85,"seasons":4}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:55,4:60]=FIELD
  for i in range(g.plots):x=7+i*7;f[27:38,x:x+6]=SEED if g.mask&(1<<i) else WEATHER;f[21:24,x:x+6]=CURSOR if i==g.cursor else FIELD;f[42:46,x:x+6]=TARGET if g.target&(1<<i) else SAFE
  f[12:16,7:7+g.season*10]=WEATHER
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q184(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.plots=self.target=self.seasons=self.cursor=self.mask=self.season=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q184",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.plots=s["plots"];self.target=s["target"];self.seasons=s["seasons"];self.cursor=self.mask=self.season=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3 and self.season==0:self.cursor=(self.cursor-1)%self.plots
  elif a==4 and self.season==0:self.cursor=(self.cursor+1)%self.plots
  elif a==5 and self.season==0:self.mask^=1<<self.cursor
  elif a==6:
   self.season+=1
   if self.season==self.seasons:
    if self.mask==self.target:self.next_level()
    else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
