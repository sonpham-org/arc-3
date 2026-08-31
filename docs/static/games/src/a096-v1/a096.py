"""a096 Shape Recovery -- order pin releases so stored strain performs work."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CHAMBER,SHAPE,PIN,STRAIN,CONSTRAINT,SOCKET,RECOVER,JAM,BAD=8,9,12,14,10,11,13,6,4,15
LEVELS=[
 {"name":"Release Pin","seq":(1,)},{"name":"Select Shape","seq":(2,)},
 {"name":"Add Constraint","seq":(3,1)},{"name":"Recovery Push","seq":(1,2,1,4,3)},
 {"name":"Release Order","seq":(2,1,3,2,1,4,3)},{"name":"Shape Recovery","seq":(1,2,3,1,4,2,1,3,4,1)},
]
def advance(s,a):
 strain,pins,positions,constraints,cursor,jams,sockets,history,snapshot=s;st=list(strain);pn=list(pins);p=list(positions);c=list(constraints)
 if a==1:
  if pn[cursor]:pn[cursor]=0;p[cursor]=min(8,p[cursor]+st[cursor]-c[cursor]);st[cursor]=max(0,st[cursor]-1)
  history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%3;history=(history+(2,))[-8:]
 elif a==3:c[cursor]^=1;history=(history+(3,))[-8:]
 elif a==4:
  for i in range(3):
   if not pn[i]:p[i]=min(8,p[i]+st[i]);st[i]=max(0,st[i]-1)
  jams=(jams+sum(int(p.count(x)>1) for x in p))%6;sockets=(sockets+sum(int(x>=7) for x in p))%7;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(st),tuple(pn),tuple(p),tuple(c),cursor,jams,sockets,history)
 return tuple(st),tuple(pn),tuple(p),tuple(c),cursor,jams,sockets,history,snapshot
for x in LEVELS:
 s=((3,2,4),(1,1,1),(0,2,4),(0,0,0),0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CHAMBER
  for i,(st,pn,p,c) in enumerate(zip(g.strain,g.pins,g.positions,g.constraints)):
   y=13+i*15;x=8+p*5;f[y:y+10,x:x+9]=SHAPE;f[y+2:y+8,x+2:x+2+st]=STRAIN
   if pn:f[y-3:y+2,x+3:x+6]=PIN
   if c:f[y-2:y+12,x+10:x+13]=CONSTRAINT
   if i==g.cursor:f[y+11:y+14,x:x+9]=RECOVER
  for x in (43,51,57):f[10:55,x:x+3]=SOCKET
  for i in range(g.jams):f[54:58,8+i*5:12+i*5]=JAM
  if g.bad:f[1:4,18:46]=BAD
  return f
class A096(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a096",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.strain,self.pins,self.positions,self.constraints,self.cursor,self.jams,self.sockets,self.history,self.snapshot=((3,2,4),(1,1,1),(0,2,4),(0,0,0),0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.strain,self.pins,self.positions,self.constraints,self.cursor,self.jams,self.sockets,self.history,self.snapshot=advance((self.strain,self.pins,self.positions,self.constraints,self.cursor,self.jams,self.sockets,self.history,self.snapshot),a)
  elif a==6:
   if (self.strain,self.pins,self.positions,self.constraints,self.cursor,self.jams,self.sockets,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
