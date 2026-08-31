"""q448 Breakwater Lineage -- carry a first intervention through two dormant subgoals."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HARBOR,CHANNEL,SKIFF,TRAIL,DORMANT,SUBGOAL,GATE,BAD=8,10,9,14,12,5,11,6,15
LEVELS=[{"name":"Dormant Split","ancestor":1,"plan":(1,4,4,5)},{"name":"Merged Echo","ancestor":2,"plan":(2,3,4,1,4,5)},{"name":"Appearance Wake","ancestor":3,"plan":(3,1,4,2,4,5)},{"name":"Branch Memory","ancestor":2,"plan":(1,3,4,2,1,4,5)},{"name":"Delayed Gate","ancestor":1,"plan":(2,1,3,4,3,2,4,5)},{"name":"Breakwater Lineage","ancestor":3,"plan":(3,1,2,4,3,1,4,2,5)}]
def advance(s,a,x):
 tokens,first,subgoals,trail,activated=s;tokens=list(tokens);trail=list(trail)
 if a in (1,2,3):
  if first is None:first=(a,tuple(tokens))
  if a==1:
   anc,look=tokens[0];tokens.append((anc,(look+1)%4))
  elif a==2 and len(tokens)>1:tokens=[(tokens[0][0],(tokens[0][1]+tokens[1][1])%4)]+tokens[2:]
  elif a==3:tokens=[(anc,(look+1)%4) for anc,look in tokens]
  trail.append((a,tuple(tokens)))
 elif a==4:subgoals+=1;trail.append((4,subgoals))
 elif a==5:
  if first is None or subgoals<2:return None
  activated=(x["ancestor"],first,subgoals,tuple(tokens),len(trail))
 return tuple(tokens),first,subgoals,tuple(trail),activated
def target(x):
 s=(((x["ancestor"],0),),None,0,(),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HARBOR;f[8:34,7:57]=CHANNEL
  for i,(anc,look) in enumerate(g.tokens[:8]):x=9+(i%4)*12;y=11+(i//4)*11;f[y:y+7,x:x+9]=SKIFF-look;f[y+7:y+9,x:x+2+anc]=TRAIL
  f[39:42,8:24]=DORMANT if g.first else CHANNEL;f[46:49,8:11+g.subgoals*12]=SUBGOAL;f[54:57,40:56]=GATE if g.activated else CHANNEL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q448(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset(1);self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q448",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self,ancestor):self.tokens=((ancestor,0),);self.first=None;self.subgoals=0;self.trail=();self.activated=None
 def on_set_level(self,l):self._reset(LEVELS[self.level_index]["ancestor"]);self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.tokens,self.first,self.subgoals,self.trail,self.activated),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.tokens,self.first,self.subgoals,self.trail,self.activated=s
  elif a==6:
   if (self.tokens,self.first,self.subgoals,self.trail,self.activated)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
