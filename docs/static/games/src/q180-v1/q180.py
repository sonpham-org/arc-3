"""q180 Gradient Climb -- navigate from local field changes without a global height map."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,PLATEAU,CLIMBER,DELTA,TRAIL,SUMMIT,GOAL,BAD=6,10,9,14,12,5,11,7,15
LEVELS=[{"name":"Rising Edge","start":(3,5),"goal":(3,3),"plateau":1,"plan":(1,1,5)},{"name":"Side Slope","start":(1,5),"goal":(4,5),"plateau":2,"plan":(4,4,4,5)},{"name":"Diagonal Hill","start":(5,5),"goal":(2,2),"plateau":2,"plan":(1,1,1,3,3,3,5)},{"name":"Broad Shelf","start":(1,1),"goal":(5,4),"plateau":3,"plan":(2,2,2,4,4,4,4,5)},{"name":"False Plateau","start":(6,5),"goal":(2,1),"plateau":4,"plan":(1,1,1,1,3,3,3,3,5)},{"name":"Gradient Climb","start":(0,6),"goal":(6,0),"plateau":5,"plan":(1,1,1,1,1,1,4,4,4,4,4,4,5)}]
def height(pos,x):
 d=abs(pos[0]-x["goal"][0])+abs(pos[1]-x["goal"][1]);return 20-d-(1 if (pos[0]+pos[1])%max(2,x["plateau"])==0 and d>1 else 0)
def advance(s,a,x):
 pos,last,changes,committed=s;changes=list(changes)
 if a in (1,2,3,4):
  dx,dy={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)}[a];new=(max(0,min(6,pos[0]+dx)),max(0,min(6,pos[1]+dy)));v=height(new,x);changes.append((new,v-last));pos=new;last=v
 elif a==5:
  if pos!=x["goal"]:return None
  committed=(pos,last,tuple(changes))
 return pos,last,tuple(changes),committed
def target(x):
 s=(x["start"],height(x["start"],x),(),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD
  for y in range(7):
   for x in range(7):f[8+y*6:13+y*6,8+x*7:14+x*7]=PLATEAU if (x+y)%3==0 else FIELD
  x,y=g.pos;f[8+y*6:13+y*6,8+x*7:14+x*7]=CLIMBER
  for i,(_,d) in enumerate(g.changes[-6:]):f[52:55,8+i*8:12+i*8]=DELTA if d>=0 else TRAIL
  f[56:59,44:56]=SUMMIT if g.committed else GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q180(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset(LEVELS[0]);self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q180",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self,x):self.pos=x["start"];self.last=height(self.pos,x);self.changes=();self.committed=None
 def on_set_level(self,l):x=LEVELS[self.level_index];self._reset(x);self.bad=False;self.target=target(x)
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.pos,self.last,self.changes,self.committed),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.pos,self.last,self.changes,self.committed=s
  elif a==6:
   if (self.pos,self.last,self.changes,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
