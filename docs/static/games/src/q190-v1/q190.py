"""q190 Lasting Shortcut -- account for a route change that persists across levels."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,NETWORK,ROUTE,TRAVEL,SHORTCUT,PERSIST,DIRECTION,GOAL,BAD=7,10,9,14,12,5,11,6,15
LEVELS=[{"name":"Open Once","goal":6,"plan":(4,1,2,5)},{"name":"Changed Street","goal":5,"plan":(1,2,5)},{"name":"Reverse Link","goal":4,"plan":(2,2,3,5)},{"name":"Global Direction","goal":5,"plan":(1,1,2,3,5)},{"name":"Lasting Detour","goal":6,"plan":(2,1,3,2,5)},{"name":"Lasting Shortcut","goal":8,"plan":(1,2,1,3,2,5)}]
def advance(s,a,x):
 position,shortcut,history,finished=s;history=list(history)
 if a in (1,2,3):delta=({1:2,2:3,3:-2} if shortcut else {1:1,2:2,3:-1})[a];position=max(0,min(12,position+delta));history.append((a,position,shortcut))
 elif a==4:
  if shortcut:return None
  shortcut=True;position+=1;history.append((4,position,shortcut))
 elif a==5:
  if position!=x["goal"]:return None
  finished=(position,shortcut,tuple(history))
 return position,shortcut,tuple(history),finished
def target(x,shortcut):
 s=(0,shortcut,(),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=NETWORK;f[12:22,8:56]=ROUTE;f[15:19,8:8+g.position*4]=TRAVEL
  f[29:36,8:56]=SHORTCUT if g.shortcut else NETWORK;f[42:45,8:24]=PERSIST;f[50:53,8:11+(len(g.history)%5)*9]=DIRECTION;f[56:59,44:56]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q190(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.shortcut=False;self._reset();self.target=target(LEVELS[0],False);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q190",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.position=0;self.history=();self.finished=None
 def on_set_level(self,l):
  if self.level_index==0:self.shortcut=False
  self._reset();self.bad=False;self.target=target(LEVELS[self.level_index],self.shortcut)
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.position,self.shortcut,self.history,self.finished),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.position,self.shortcut,self.history,self.finished=s
  elif a==6:
   if (self.position,self.shortcut,self.history,self.finished)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
