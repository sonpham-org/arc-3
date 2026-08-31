"""q523 Impeller Frame -- compose blade motion with counter-rotating wake frames."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,RING,BLADE,RIDER,WAKE,SAMPLE,COST,GOAL,BAD=0,9,10,11,14,6,12,7,13,15
LEVELS=[
 {"name":"First Blade","seq":(1,)},{"name":"Outer Ring","seq":(2,1)},
 {"name":"Reversed Wake","seq":(1,3,1)},{"name":"Costed Alignment","seq":(1,4,3,2,1)},
 {"name":"Counter Rotation","seq":(1,3,1,4,2,3,1)},
 {"name":"Impeller Frame","seq":(2,1,3,4,1,2,3,1,4)}]
def advance(s,a):
 ring,pos,wake,evidence,cost,locked=s
 if a==1:pos=(pos+(1 if (wake+ring)%2==0 else -1))%12
 elif a==2:ring^=1;pos=(11-pos)%12
 elif a==3:wake=(wake+1)%4;pos=(pos+ring)%12
 elif a==4:
  costly=len(evidence)>=2 and evidence[-1]==evidence[-2];evidence=evidence+((pos+ring+wake)%3,);cost+=2 if costly else 1
 elif a==5:locked=(ring,pos,wake,evidence,cost)
 return ring,pos,wake,evidence,cost,locked
for x in LEVELS:
 s=(0,0,0,(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["target"]=s[:-1];x["plan"]=x["seq"]+(5,)
def target(x):
 s=(0,0,0,(),0,None)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD
  for i in range(12):
   x=8+(i%6)*9;y=9+(i//6)*18;f[y:y+6,x:x+6]=RIDER if i==g.pos else (BLADE if (i+g.wake)%2 else RING)
  f[38:42,8:56]=WAKE;f[39:41,8+g.wake*11:17+g.wake*11]=BLADE
  for i,v in enumerate(g.evidence[-5:]):f[47:52,8+i*10:15+i*10]=SAMPLE if v%2 else RING
  f[54:58,8:8+min(g.cost,9)*5]=COST
  if g.locked:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q523(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q523",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.ring=self.pos=self.wake=self.cost=0;self.evidence=();self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.ring,self.pos,self.wake,self.evidence,self.cost,self.locked=advance((self.ring,self.pos,self.wake,self.evidence,self.cost,self.locked),a)
  elif a==6:
   if (self.ring,self.pos,self.wake,self.evidence,self.cost,self.locked)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
