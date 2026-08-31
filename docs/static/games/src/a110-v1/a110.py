"""a110 Mobile Cover -- phase patrol footprints across a timed target window."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FIELD,TARGET,PATROL,FOOTPRINT,FORBIDDEN,COVERED,PHASE,WINDOW,BAD=6,8,9,12,14,4,13,11,10,15
LEVELS=[
 {"name":"Move Patrol","seq":(1,)},{"name":"Change Phase","seq":(2,)},
 {"name":"Select Sentry","seq":(3,1)},{"name":"Run Window","seq":(1,2,3,1,4)},
 {"name":"Avoid Forbidden","seq":(2,1,3,2,1,4,3)},{"name":"Mobile Cover","seq":(1,2,3,1,4,2,3,1,4,2)},
]
def advance(s,a):
 locations,phases,cursor,coverage,forbidden,clock,history,snapshot=s;loc=list(locations);ph=list(phases)
 if a==1:loc[cursor]=(loc[cursor]+1)%9;history=(history+(1,))[-8:]
 elif a==2:ph[cursor]=(ph[cursor]+1)%4;history=(history+(2,))[-8:]
 elif a==3:cursor=(cursor+1)%3;history=(history+(3,))[-8:]
 elif a==4:
  cov=coverage;bad=forbidden
  for t in range(4):
   for i in range(3):cell=(loc[i]+ph[i]+t*(i+1))%9;cov|=1<<cell;bad+=int(cell in (2,7))
  coverage=cov;forbidden=bad%7;clock=(clock+4)%12;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(loc),tuple(ph),cursor,coverage,forbidden,clock,history)
 return tuple(loc),tuple(ph),cursor,coverage,forbidden,clock,history,snapshot
for x in LEVELS:
 s=((0,3,6),(0,1,2),0,0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD
  for i in range(9):x=10+(i%3)*16;y=12+(i//3)*15;col=FORBIDDEN if i in (2,7) else COVERED if g.coverage&(1<<i) else TARGET;f[y:y+12,x:x+12]=col
  for i,p in enumerate(g.locations):x=13+(p%3)*16;y=15+(p//3)*15;f[y:y+6,x:x+6]=PATROL;ifill=PHASE if i==g.cursor else FOOTPRINT;f[y-4:y-1,x-2:x+8]=ifill
  f[53:57,8:8+g.clock*4]=WINDOW;f[7:10,8:8+g.forbidden*6]=BAD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A110(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a110",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.locations,self.phases,self.cursor,self.coverage,self.forbidden,self.clock,self.history,self.snapshot=((0,3,6),(0,1,2),0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.locations,self.phases,self.cursor,self.coverage,self.forbidden,self.clock,self.history,self.snapshot=advance((self.locations,self.phases,self.cursor,self.coverage,self.forbidden,self.clock,self.history,self.snapshot),a)
  elif a==6:
   if (self.locations,self.phases,self.cursor,self.coverage,self.forbidden,self.clock,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
