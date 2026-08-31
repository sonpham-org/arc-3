"""q602 Lockwater Grammar -- compose barge commands while causal identities swap appearance."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CANAL,WATER,BARGE,LOCK,GLYPH,IDENTITY,GOAL,BAD=3,10,11,14,8,6,12,13,15
LEVELS=[{"name":"One Glyph","seq":(1,)},{"name":"Grouped Pair","seq":(2,1)},{"name":"Identity Crossing","seq":(3,1,2)},{"name":"Relay Clause","seq":(1,4,2,3)},{"name":"Coupled Locks","seq":(2,1,4,3,2,1)},{"name":"Lockwater Grammar","seq":(1,3,2,4,1,2,3,4,2)}]
def advance(s,a):
 identities,positions,levels,message,relay,parsed=s;ids=list(identities);pos=list(positions);lev=list(levels)
 if a==1:message=message+((1,relay),);pos[ids[0]]=(pos[ids[0]]+1+lev[0])%6;lev[0]=(lev[0]+1)%4
 elif a==2:message=message+((2,len(message)%3),);pos[ids[1]]=(pos[ids[1]]+2+lev[1])%6;lev[1]=(lev[1]+lev[0]+1)%4
 elif a==3:ids[0],ids[1]=ids[1],ids[0];pos[0],pos[1]=pos[1],pos[0];message=message+((3,tuple(ids)),)
 elif a==4:relay=(relay+len(message)+sum(lev))%4;message=message+((4,relay),)
 elif a==5:parsed=(tuple(ids),tuple(pos),tuple(lev),message[-5:],relay)
 return tuple(ids),tuple(pos),tuple(lev),message,relay,parsed
for x in LEVELS:
 s=((0,1),(0,3),(0,1),(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CANAL
  for lane in range(2):y=9+lane*15;f[y:y+11,7:57]=WATER;f[y:y+11,30:34]=LOCK;i=g.identities[lane];x=8+g.positions[i]*8;f[y+3:y+9,x:x+7]=BARGE;f[y+4:y+7,x+2:x+5]=IDENTITY if i else GLYPH
  for i,item in enumerate(g.message[-5:]):x=7+i*10;f[39:45,x:x+8]=GLYPH;f[46:49,x:x+2+item[0]]=LOCK
  f[52:56,8:8+g.relay*12+9]=IDENTITY
  if g.parsed:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q602(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q602",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.identities=(0,1);self.positions=(0,3);self.levels=(0,1);self.message=();self.relay=0;self.parsed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.identities,self.positions,self.levels,self.message,self.relay,self.parsed=advance((self.identities,self.positions,self.levels,self.message,self.relay,self.parsed),a)
  elif a==6:
   if (self.identities,self.positions,self.levels,self.message,self.relay,self.parsed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
