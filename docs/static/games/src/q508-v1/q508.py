"""q508 Breakwater Frame -- carry a dormant intervention across two solved harbor subgoals."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HARBOR,CHANNEL,SKIFF,FRAME,DORMANT,SUBGOAL,GOAL,BAD=14,10,9,12,5,11,6,7,15
LEVELS=[{"name":"Dormant Gate","plan":(4,5,5)},{"name":"Local Skiff","plan":(1,4,5,2,5)},{"name":"Rotated Channel","plan":(3,4,1,5,2,5)},{"name":"Delayed Crossing","plan":(2,4,5,3,1,5)},{"name":"Carried Cause","plan":(1,3,4,2,5,1,5)},{"name":"Breakwater Frame","plan":(3,1,4,2,5,3,1,5)}]
def advance(s,a):
 skiffs,rotation,offset,dormant,subgoals,unlocked=s;skiffs=list(skiffs)
 if a in (1,2):i=(a-1+rotation)%3;skiffs[i]=(skiffs[i]+(1 if a==1 else -1)+offset)%5
 elif a==3:rotation=(rotation+1)%4;skiffs=skiffs[1:]+skiffs[:1]
 elif a==4:
  offset=(offset+1)%5
  if dormant<0:dormant=(sum(skiffs)+rotation+offset)%5
 elif a==5:
  subgoals+=1
  if subgoals>=2 and dormant>=0 and not unlocked:skiffs=[(v+dormant+rotation+offset)%5 for v in skiffs];unlocked=True
 return tuple(skiffs),rotation,offset,dormant,subgoals,unlocked
def target(x):
 s=((0,2,4),0,0,-1,0,False)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HARBOR;f[8:15,8:56]=CHANNEL
  for i,v in enumerate(g.skiffs):x=8+i*18;f[20:39,x:x+14]=CHANNEL;f[24+v*3:29+v*3,x+3:x+11]=SKIFF-i
  f[43:46,8:11+g.rotation*11]=FRAME;f[49:52,8:11+max(0,g.dormant)*10]=DORMANT;f[54:57,8:11+min(g.subgoals,3)*14]=SUBGOAL;f[58:60,48:56]=GOAL if g.unlocked else CHANNEL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q508(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q508",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.skiffs=(0,2,4);self.rotation=self.offset=self.subgoals=0;self.dormant=-1;self.unlocked=False
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.skiffs,self.rotation,self.offset,self.dormant,self.subgoals,self.unlocked=advance((self.skiffs,self.rotation,self.offset,self.dormant,self.subgoals,self.unlocked),a)
  elif a==6:
   if (self.skiffs,self.rotation,self.offset,self.dormant,self.subgoals,self.unlocked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
