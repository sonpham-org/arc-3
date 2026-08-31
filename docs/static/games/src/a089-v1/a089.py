"""a089 Memory Cloth -- accumulate permanent deformation through pulls and releases."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FRAME,CLOTH,PEG,PULL,MEMORY,CREASE,TARGET,THREAD,BAD=1,8,9,14,12,10,11,13,6,15
LEVELS=[
 {"name":"Pull Cloth","seq":(1,)},{"name":"Move Peg","seq":(3,)},
 {"name":"Release Memory","seq":(1,4)},{"name":"Train Crease","seq":(1,3,1,4,2)},
 {"name":"Repeated Pulls","seq":(1,1,3,2,4,1,4)},{"name":"Memory Cloth","seq":(1,3,1,4,2,3,1,4,1,4)},
]
def advance(s,a):
 deform,memory,cursor,tension,creases,history,snapshot=s;d=list(deform);m=list(memory)
 if a==1:d[cursor]=min(5,d[cursor]+1);tension=(tension+1)%7;history=(history+(1,))[-8:]
 elif a==2:d[cursor]=max(-3,d[cursor]-1);tension=max(0,tension-1);history=(history+(2,))[-8:]
 elif a==3:cursor=(cursor+1)%6;history=(history+(3,))[-8:]
 elif a==4:
  for i in range(6):m[i]=max(-3,min(5,m[i]+(d[i]-m[i])//2));d[i]=m[i]
  creases=(creases+(sum(abs(x) for x in m)%5,))[-6:];tension=0;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(d),tuple(m),cursor,tension,creases,history)
 return tuple(d),tuple(m),cursor,tension,creases,history,snapshot
for x in LEVELS:
 s=((0,0,0,0,0,0),(0,0,0,0,0,0),0,0,(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FRAME;pts=[]
  for i,v in enumerate(g.deform):x=14+(i%3)*18;y=18+(i//3)*25+v*2;pts.append((x,y));f[y-3:y+4,x-3:x+4]=PULL if i==g.cursor else PEG
  for u,v in ((0,1),(1,2),(3,4),(4,5),(0,3),(1,4),(2,5),(0,4),(1,5)):
   x1,y1=pts[u];x2,y2=pts[v]
   for j in range(13):x=x1+(x2-x1)*j//12;y=y1+(y2-y1)*j//12;f[y:y+2,x:x+2]=CLOTH if u<3 else THREAD
  f[8:12,8:8+g.tension*6]=MEMORY
  for i,v in enumerate(g.creases):f[53:57,8+i*8:14+i*8]=CREASE
  f[47:51,45:57]=TARGET
  if g.bad:f[1:4,18:46]=BAD
  return f
class A089(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a089",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.deform,self.memory,self.cursor,self.tension,self.creases,self.history,self.snapshot=((0,0,0,0,0,0),(0,0,0,0,0,0),0,0,(),(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.deform,self.memory,self.cursor,self.tension,self.creases,self.history,self.snapshot=advance((self.deform,self.memory,self.cursor,self.tension,self.creases,self.history,self.snapshot),a)
  elif a==6:
   if (self.deform,self.memory,self.cursor,self.tension,self.creases,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
