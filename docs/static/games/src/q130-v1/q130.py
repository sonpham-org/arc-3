"""q130 Rhythm Rival -- vary cadence deliberately to open a safe timing window."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARENA,RIVAL,PULSE,CADENCE,WINDOW,STRIKE,GOAL,BAD=1,10,9,14,6,4,11,7,15
LEVELS=[{"name":"Three Beats","plan":(1,2,3,5)},{"name":"Reordered Beat","plan":(2,1,3,5)},{"name":"False Rhythm","plan":(3,1,2,1,2,3,5)},{"name":"Held Opening","plan":(4,1,3,2,5)},{"name":"Broken Cadence","plan":(1,1,4,2,3,1,5)},{"name":"Rhythm Rival","plan":(4,2,4,1,3,2,5)}]
def advance(s,a):
 cadence,rival,window,strike=s;cadence=list(cadence)
 if a in (1,2,3,4):cadence.append(a);recent=cadence[-3:];rival=(sum(recent)+len(cadence))%3;window=len(recent)==3 and set(recent)=={1,2,3}
 elif a==5:
  if not window:return None
  strike=(tuple(cadence[-3:]),rival,len(cadence))
 return tuple(cadence),rival,window,strike
def target(x):
 s=((),0,False,None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ARENA;f[8:31,7:29]=RIVAL
  for i,a in enumerate(g.cadence[-8:]):x=34+(i%4)*6;y=11+(i//4)*11;f[y:y+7,x:x+4]=PULSE-a
  f[37:40,8:11+g.rival*14]=CADENCE;f[45:48,8:24]=WINDOW if g.window else RIVAL;f[53:56,40:56]=STRIKE if g.strike else GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q130(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q130",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.cadence=();self.rival=0;self.window=False;self.strike=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.cadence,self.rival,self.window,self.strike),a)
   if s is None:self.bad=True;self.lose()
   else:self.cadence,self.rival,self.window,self.strike=s
  elif a==6:
   if (self.cadence,self.rival,self.window,self.strike)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
