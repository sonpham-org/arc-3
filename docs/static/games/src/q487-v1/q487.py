"""q487 Archive Staircase -- solve ordered subgoals under a shifting glyph dictionary."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,STEP,GLYPH,SEALED,SHIFT,BAD=12,7,10,15,14,11,8
LEVELS=[{"name":n,"needs":needs} for n,needs in [
 ("First Folio",((0,),)),("Indexed Landing",((1,),(2,0))),
 ("Ordered Shelves",((2,),(0,1),(2,1))),("Nested Catalogue",((1,0),(2,),(0,2,1))),
 ("Revised Dictionary",((2,1),(0,),(1,2),(0,1))),
 ("Archive Staircase",((0,2),(1,),(2,0,1),(1,2),(0,1,2)))]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=ARCHIVE
  for i in range(len(LEVELS[g.level_index]["needs"])):
   x=7+i*9;f[11+i*2:21+i*2,x:x+7]=SEALED if i<g.stage else STEP
  for i,v in enumerate(g.entry):f[37:43,8+i*10:16+i*10]=GLYPH if v%2 else SHIFT
  f[51:56,8:8+g.shift*15]=SHIFT
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q487(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.stage=self.shift=0;self.entry=[];self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q487",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.stage=self.shift=0;self.entry=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.entry.append((a-1+self.shift)%3)
  elif a==5:
   if self.entry:self.entry.pop()
  elif a==4:
   if self.stage<len(x["needs"]) and tuple(self.entry)==x["needs"][self.stage]:self.stage+=1;self.shift=(self.shift+1)%3;self.entry=[]
   else:self.bad=True;self.lose()
  elif a==6:
   if self.stage==len(x["needs"]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
