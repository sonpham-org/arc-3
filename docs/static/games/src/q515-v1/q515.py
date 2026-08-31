"""q515 Waystation Frame -- compose local caravan motion with shifting dune corridors."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SAND,DUNE,WALKER,LANE,FRAME,POLICY,GOAL,BAD=0,12,11,14,10,6,9,13,15
LEVELS=[
 {"name":"First Crossing","seq":(1,)},{"name":"Local Choice","seq":(2,1)},
 {"name":"Shifted Corridor","seq":(1,2,3,1)},{"name":"Changed Lane","seq":(1,4,2,2)},
 {"name":"Repeat Counter","seq":(1,2,1,3,2,4,1)},
 {"name":"Waystation Frame","seq":(2,1,2,3,1,4,2,1,3)}]
def advance(s,a):
 lane,dist,frame,recent,locked=s
 if a in (1,2):
  choice=a-1;punished=len(recent)==2 and recent[0]==recent[1]==choice;delta=-1 if punished else 1+int(frame==choice)
  dist=max(0,min(12,dist+delta));lane=(lane+(1 if (choice+frame)%2==0 else -1))%3;recent=(recent+(choice,))[-2:]
 elif a==3:frame^=1
 elif a==4:lane=(lane+1)%3
 elif a==5:locked=(lane,dist,frame,recent)
 return lane,dist,frame,recent,locked
for x in LEVELS:
 s=(1,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["target"]=(s[0],s[1],s[2],s[3]);x["plan"]=x["seq"]+(5,)
def target(x):
 s=(1,0,0,(),None)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SAND
  for i in range(3):y=10+i*12;f[y:y+7,8:56]=DUNE;f[y+2:y+5,10:54]=LANE
  y=10+g.lane*12;x=10+min(g.dist,11)*4;f[y:y+7,x:x+4]=WALKER
  f[47:51,8:8+g.frame*18+12]=FRAME
  for i,v in enumerate(g.recent):f[54:58,8+i*13:18+i*13]=POLICY if v else LANE
  if g.locked:f[54:59,41:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q515(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q515",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.lane=1;self.dist=self.frame=0;self.recent=();self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.lane,self.dist,self.frame,self.recent,self.locked=advance((self.lane,self.dist,self.frame,self.recent,self.locked),a)
  elif a==6:
   if (self.lane,self.dist,self.frame,self.recent,self.locked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
